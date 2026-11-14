import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import List, Optional, Type, Union

from assets import (
    Account,
    Assistant,
    BuilderApprentice,
    BuilderBite,
    BuilderPotion,
    ClockTower,
    Helper,
    LabPotion,
    LabAssistant,
    PetPotion,
    StudySoup,
    SUBCATEGORIES,
    TimedBoost,
    Timer,
    VILLAGES,
)


def _load_assistant(record: object, name: str, account_name: str):
    if not isinstance(record, dict):
        raise ValueError(f"{name} data for account {account_name!r} must be an object.")

    active = record.get("active", False)
    assigned = record.get("assigned", False)
    cooldown = record.get("cooldown", 0)
    multiplier = record.get("multiplier", 1)
    if not isinstance(active, bool) or not isinstance(assigned, bool):
        raise ValueError(
            f"{name} active and assigned values for account {account_name!r} "
            "must be booleans."
        )
    if isinstance(cooldown, bool) or not isinstance(cooldown, int) or cooldown < 0:
        raise ValueError(
            f"{name} cooldown for account {account_name!r} "
            "must be a non-negative integer."
        )
    if isinstance(multiplier, bool) or not isinstance(multiplier, int) or multiplier < 0:
        raise ValueError(
            f"{name} multiplier for account {account_name!r} "
            "must be a non-negative integer."
        )
    return active, assigned, cooldown, multiplier


def _remaining_seconds(
    record: dict,
    helper_name: str,
    account_name: str,
    now: float,
) -> int:
    ends_at = record.get("ends_at")
    if (
        isinstance(ends_at, bool)
        or not isinstance(ends_at, (int, float))
        or not math.isfinite(ends_at)
        or ends_at < 0
    ):
        raise ValueError(
            f"{helper_name} end time for account {account_name!r} "
            "must be a non-negative timestamp."
        )
    return max(0, math.ceil(ends_at - now))


def _elapse_cycling_helper(helper: Helper, elapsed_seconds: int) -> None:
    if elapsed_seconds <= 0:
        return
    phase_seconds = helper.cooldown or (
        helper.active_cooldown if helper.active else helper.inactive_cooldown
    )
    if elapsed_seconds < phase_seconds:
        helper.cooldown = phase_seconds - elapsed_seconds
        return

    remaining = elapsed_seconds - phase_seconds
    helper.active = not helper.active
    phase_seconds = (
        helper.active_cooldown if helper.active else helper.inactive_cooldown
    )
    cycle_seconds = helper.active_cooldown + helper.inactive_cooldown
    if cycle_seconds:
        remaining %= cycle_seconds
    while remaining >= phase_seconds:
        remaining -= phase_seconds
        helper.active = not helper.active
        phase_seconds = (
            helper.active_cooldown if helper.active else helper.inactive_cooldown
        )
    helper.cooldown = phase_seconds - remaining


def _restore_helper_cooldown(
    helper: Helper,
    record: dict,
    helper_name: str,
    account_name: str,
    now: float,
    elapsed_seconds: int,
    cycles_when_unassigned: bool = False,
) -> None:
    if "ends_at" not in record:
        if isinstance(helper, Assistant) and helper.assigned:
            _elapse_cycling_helper(helper, elapsed_seconds)
        elif cycles_when_unassigned and helper.cooldown > 0:
            _elapse_cycling_helper(helper, elapsed_seconds)
        else:
            helper.cooldown = max(0, helper.cooldown - elapsed_seconds)
        return

    ends_at = record["ends_at"]
    helper.cooldown = _remaining_seconds(record, helper_name, account_name, now)
    if ends_at <= now:
        if not cycles_when_unassigned and (
            not isinstance(helper, Assistant) or not helper.assigned
        ):
            helper.cooldown = 0
            helper.active = False
            return
        helper.active = not helper.active
        helper.cooldown = (
            helper.active_cooldown if helper.active else helper.inactive_cooldown
        )
        _elapse_cycling_helper(helper, math.floor(now - ends_at))


def _load_timed_boost(
    record: object,
    helper_name: str,
    helper_type: Type[TimedBoost],
    account_name: str,
    now: float,
    elapsed_seconds: int,
    cycles_when_unassigned: bool = False,
) -> TimedBoost:
    if not isinstance(record, dict):
        raise ValueError(
            f"{helper_name} data for account {account_name!r} must be an object."
        )

    active = record.get("active", False)
    if not isinstance(active, bool):
        raise ValueError(
            f"{helper_name} active value for account {account_name!r} "
            "must be a boolean."
        )
    cooldown = record.get("cooldown", 0)
    if isinstance(cooldown, bool) or not isinstance(cooldown, int) or cooldown < 0:
        raise ValueError(
            f"{helper_name} cooldown for account {account_name!r} "
            "must be a non-negative integer."
        )
    helper = helper_type(active=active, cooldown=cooldown)
    _restore_helper_cooldown(
        helper,
        record,
        helper_name,
        account_name,
        now,
        elapsed_seconds,
        cycles_when_unassigned,
    )
    if helper.cooldown == 0:
        helper.active = False
    return helper


def _account_helpers(account: Account) -> List[Helper]:
    return [
        account.builder_apprentice,
        account.lab_assistant,
        account.clock_tower,
        account.builder_potion,
        account.builder_bite,
        account.lab_potion,
        account.study_soup,
        account.pet_potion,
    ]


def _sync_account_helpers(account: Account) -> None:
    for timer in account.timers:
        for helper in _account_helpers(account):
            assigned = (
                isinstance(helper, Assistant)
                and helper.assigned
                and helper.assigned_timer is timer
            )
            active = (
                assigned and helper.active
                if isinstance(helper, Assistant)
                else helper.active
            )
            timer.sync_helper(
                helper,
                assigned=assigned,
                active=active,
            )


def _simulate_elapsed(account: Account, elapsed_seconds: int) -> None:
    if elapsed_seconds <= 0:
        _sync_account_helpers(account)
        for timer in account.timers:
            timer.recalculate_actual_time_left()
        return

    _sync_account_helpers(account)
    remaining = elapsed_seconds
    assistants = (account.builder_apprentice, account.lab_assistant)
    boosts = (
        account.builder_potion,
        account.builder_bite,
        account.lab_potion,
        account.study_soup,
        account.pet_potion,
    )
    while remaining > 0:
        ticks = remaining
        for timer in account.timers:
            if timer.value > 0:
                ticks = min(
                    ticks,
                    (timer.value + timer.rate - 1) // timer.rate,
                )
        for helper in (*assistants, account.clock_tower):
            if helper.cooldown > 0:
                ticks = min(ticks, helper.cooldown)
        for boost in boosts:
            if boost.active and boost.cooldown > 0:
                ticks = min(ticks, boost.cooldown)

        for timer in account.timers:
            timer.value = max(0, timer.value - timer.rate * ticks)
            timer.actual_time_left = max(0, timer.actual_time_left - ticks)

        for assistant in assistants:
            if (
                assistant.assigned_timer is not None
                and assistant.assigned_timer.value == 0
            ):
                assistant.cooldown = max(
                    0, assistant.cooldown - (ticks - 1)
                )
                assistant.assigned = False
                assistant.assigned_timer = None
                if assistant.active:
                    assistant.active = False
                    assistant.cooldown = assistant.inactive_cooldown
            elif assistant.cooldown > 0:
                assistant.cooldown -= ticks
                if assistant.cooldown == 0 and assistant.assigned:
                    assistant.active = not assistant.active
                    assistant.cooldown = (
                        assistant.active_cooldown
                        if assistant.active
                        else assistant.inactive_cooldown
                    )

        if account.clock_tower.cooldown > 0:
            account.clock_tower.cooldown -= ticks
            if account.clock_tower.cooldown == 0:
                account.clock_tower.active = not account.clock_tower.active
                account.clock_tower.cooldown = (
                    account.clock_tower.active_cooldown
                    if account.clock_tower.active
                    else account.clock_tower.inactive_cooldown
                )

        for boost in boosts:
            if boost.active:
                boost.cooldown = max(0, boost.cooldown - ticks)
                if boost.cooldown == 0:
                    boost.active = False

        remaining -= ticks
        _sync_account_helpers(account)

    for timer in account.timers:
        timer.recalculate_actual_time_left()


def load_accounts(file_path: Optional[Union[str, Path]] = None) -> List[Account]:
    path = Path(file_path) if file_path is not None else Path(__file__).with_name("data.json")

    with path.open("r", encoding="utf-8") as data_file:
        records = json.load(data_file)
    now = time.time()

    if not isinstance(records, list):
        raise ValueError("The timer data must contain a list of accounts.")

    accounts: List[Account] = []
    for account_index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"Account at index {account_index} must be an object.")

        name = record.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Account at index {account_index} must have a non-empty name.")

        saved_at = record.get("saved_at")
        if saved_at is not None and (
            isinstance(saved_at, bool)
            or not isinstance(saved_at, (int, float))
            or not math.isfinite(saved_at)
            or saved_at < 0
        ):
            raise ValueError(
                f"Account {name!r} saved_at must be a non-negative timestamp."
            )
        elapsed_seconds = 0
        simulation_seconds = (
            max(0, int(now - saved_at)) if saved_at is not None else 0
        )

        exported_at = record.get("exported_at")
        if saved_at is None and exported_at is not None and (
            isinstance(exported_at, bool)
            or not isinstance(exported_at, (int, float))
            or not math.isfinite(exported_at)
            or exported_at < 0
        ):
            raise ValueError(
                f"Account {name!r} exported_at must be a non-negative timestamp."
            )
        elif saved_at is None and exported_at is not None:
            elapsed_seconds = max(0, int(now - exported_at))
        helper_elapsed_seconds = elapsed_seconds if saved_at is None else 0

        tag = record.get("tag")
        if tag is not None and not isinstance(tag, str):
            raise ValueError(f"Account {name!r} tag must be a string.")

        timers: List[Timer] = []
        builder_apprentice = BuilderApprentice()
        lab_assistant = LabAssistant()
        clock_tower = ClockTower()
        builder_potion = BuilderPotion()
        builder_bite = BuilderBite()
        lab_potion = LabPotion()
        study_soup = StudySoup()
        pet_potion = PetPotion()
        for village in VILLAGES:
            village_record = record.get(village)
            if not isinstance(village_record, dict):
                raise ValueError(f"Account {name!r} must have categories for {village!r}.")

            if village == "Builder Base":
                tower_record = village_record.get("clock_tower", {})
                if not isinstance(tower_record, dict):
                    raise ValueError(
                        f"Clock Tower data for account {name!r} must be an object."
                    )
                active = tower_record.get("active", False)
                cooldown = tower_record.get("cooldown", 0)
                active_cooldown_minutes = tower_record.get(
                    "active_cooldown_minutes", 30
                )
                if not isinstance(active, bool):
                    raise ValueError(
                        f"Clock Tower active value for account {name!r} must be a boolean."
                    )
                if isinstance(cooldown, bool) or not isinstance(cooldown, int) or cooldown < 0:
                    raise ValueError(
                        f"Clock Tower cooldown for account {name!r} "
                        "must be a non-negative integer."
                    )
                if (
                    isinstance(active_cooldown_minutes, bool)
                    or not isinstance(active_cooldown_minutes, int)
                    or active_cooldown_minutes < 0
                ):
                    raise ValueError(
                        f"Clock Tower active cooldown for account {name!r} "
                        "must be a non-negative integer."
                    )
                clock_tower = ClockTower(
                    active=active,
                    cooldown=cooldown,
                    active_cooldown_minutes=active_cooldown_minutes,
                )
                _restore_helper_cooldown(
                    clock_tower,
                    tower_record,
                    "Clock Tower",
                    name,
                    now,
                    helper_elapsed_seconds,
                    cycles_when_unassigned=True,
                )

            for category in SUBCATEGORIES[village]:
                category_record = village_record.get(category)
                helper_name = None
                helper_type = None
                assistant: Optional[Assistant] = None
                helper_record = {}
                if village == "Home Village" and category == "Building":
                    helper_name = "Builder Apprentice"
                    helper_type = BuilderApprentice
                    if not isinstance(category_record, dict):
                        raise ValueError(
                            f"Account {name!r} must define Home Village Building data."
                        )
                    timer_records = category_record.get("timers")
                    helper_record = category_record.get("builder_apprentice", {})
                    builder_potion = _load_timed_boost(
                        category_record.get("builder_potion", {}),
                        "Builder Potion",
                        BuilderPotion,
                        name,
                        now,
                        helper_elapsed_seconds,
                    )
                    builder_bite = _load_timed_boost(
                        category_record.get("builder_bite", {}),
                        "Builder Bite",
                        BuilderBite,
                        name,
                        now,
                        helper_elapsed_seconds,
                    )
                elif village == "Home Village" and category == "Lab":
                    helper_name = "Lab Assistant"
                    helper_type = LabAssistant
                    if not isinstance(category_record, dict):
                        raise ValueError(
                            f"Account {name!r} must define Home Village Lab data."
                        )
                    timer_records = category_record.get("timers")
                    helper_record = category_record.get("lab_assistant", {})
                    lab_potion = _load_timed_boost(
                        category_record.get("lab_potion", {}),
                        "Lab Potion",
                        LabPotion,
                        name,
                        now,
                        helper_elapsed_seconds,
                    )
                    study_soup = _load_timed_boost(
                        category_record.get("study_soup", {}),
                        "Study Soup",
                        StudySoup,
                        name,
                        now,
                        helper_elapsed_seconds,
                    )
                elif village == "Home Village" and category == "Pet":
                    if isinstance(category_record, dict):
                        timer_records = category_record.get("timers")
                        pet_potion = _load_timed_boost(
                            category_record.get("pet_potion", {}),
                            "Pet Potion",
                            PetPotion,
                            name,
                            now,
                            elapsed_seconds,
                        )
                    else:
                        timer_records = category_record
                elif village == "Builder Base" and isinstance(category_record, dict):
                    timer_records = category_record.get("timers")
                else:
                    timer_records = category_record

                if helper_name is not None and helper_type is not None:
                    values = _load_assistant(helper_record, helper_name, name)
                    active, assigned, cooldown, multiplier = values
                    helper = helper_type(
                        active=active,
                        assigned=assigned,
                        cooldown=cooldown,
                        multiplier=multiplier,
                    )
                    _restore_helper_cooldown(
                        helper,
                        helper_record,
                        helper_name,
                        name,
                        now,
                        helper_elapsed_seconds,
                    )
                    assistant = helper
                    if helper_type is BuilderApprentice:
                        builder_apprentice = helper
                    else:
                        lab_assistant = helper

                if not isinstance(timer_records, list):
                    raise ValueError(
                        f"Account {name!r} must have a list of timers "
                        f"for {village!r} / {category}."
                    )

                category_timers: List[Timer] = []
                for timer_index, timer_record in enumerate(timer_records):
                    if not isinstance(timer_record, dict):
                        raise ValueError(
                            f"Timer at index {timer_index} in {village!r} / "
                            f"{category} for account {name!r} must be an object."
                        )

                    timer_name = timer_record.get("name")
                    value = timer_record.get("value")
                    if not isinstance(timer_name, str) or not timer_name.strip():
                        raise ValueError(
                            f"Timer at index {timer_index} in {village!r} / "
                            f"{category} for account {name!r} must have a non-empty name."
                        )
                    if "ends_at" in timer_record:
                        ends_at = timer_record["ends_at"]
                        if (
                            isinstance(ends_at, bool)
                            or not isinstance(ends_at, (int, float))
                            or not math.isfinite(ends_at)
                            or ends_at < 0
                        ):
                            raise ValueError(
                                f"Timer {timer_name!r} in {village!r} / {category} "
                                f"for account {name!r} must have a non-negative "
                                "end timestamp."
                            )
                        remaining = max(0, math.ceil(ends_at - now))
                    else:
                        if (
                            isinstance(value, bool)
                            or not isinstance(value, int)
                            or value < 0
                        ):
                            raise ValueError(
                                f"Timer {timer_name!r} in {village!r} / {category} "
                                f"for account {name!r} must have a non-negative "
                                "integer value in seconds."
                            )
                        remaining = max(
                            0,
                            value - (elapsed_seconds if saved_at is None else 0),
                        )

                    timer = Timer(
                        name=timer_name,
                        value=remaining,
                        village=village,
                        category=category,
                    )
                    timers.append(timer)
                    category_timers.append(timer)

                if helper_name is not None and assistant is not None:
                    assigned_timer = helper_record.get("assigned_timer")
                    if assigned_timer is not None:
                        if not isinstance(assigned_timer, dict):
                            raise ValueError(
                                f"{helper_name} assigned timer for account {name!r} "
                                "must be an object."
                            )
                        assigned_timer_index = assigned_timer.get("index")
                        assigned_timer_name = assigned_timer.get("name")
                        if (
                            isinstance(assigned_timer_index, bool)
                            or not isinstance(assigned_timer_index, int)
                            or not 0 <= assigned_timer_index < len(category_timers)
                        ):
                            raise ValueError(
                                f"{helper_name} assigned timer index for account "
                                f"{name!r} is outside the {village!r} / {category} "
                                "timer list."
                            )
                        assigned_timer_object = category_timers[assigned_timer_index]
                        if assigned_timer_name != assigned_timer_object.name:
                            raise ValueError(
                                f"{helper_name} assigned timer name for account "
                                f"{name!r} does not match the timer at index "
                                f"{assigned_timer_index}."
                            )
                        if not assistant.assigned:
                            raise ValueError(
                                f"{helper_name} has an assigned timer but is marked "
                                "unassigned."
                            )
                        assistant.assigned_timer = assigned_timer_object
                    if (
                        assistant.assigned_timer is not None
                        and assistant.assigned_timer.value == 0
                    ):
                        assistant.assigned = False
                        assistant.assigned_timer = None
                        if assistant.active:
                            assistant.active = False
                            assistant.cooldown = assistant.inactive_cooldown

        account = Account(
            name=name,
            tag=tag,
            timers=timers,
            builder_apprentice=builder_apprentice,
            lab_assistant=lab_assistant,
            clock_tower=clock_tower,
            builder_potion=builder_potion,
            builder_bite=builder_bite,
            lab_potion=lab_potion,
            study_soup=study_soup,
            pet_potion=pet_potion,
        )
        if saved_at is not None:
            _simulate_elapsed(account, simulation_seconds)
        accounts.append(account)

    return accounts


def _serialize_timer(timer: Timer) -> dict:
    return {"name": timer.name, "value": max(0, timer.value)}


def _serialize_assistant(
    assistant: Assistant,
    category_timers: List[Timer],
) -> dict:
    record = {
        "active": assistant.active,
        "assigned": assistant.assigned,
        "cooldown": max(0, assistant.cooldown),
        "multiplier": assistant.multiplier,
    }
    if assistant.assigned_timer is not None:
        try:
            timer_index = next(
                index
                for index, timer in enumerate(category_timers)
                if timer is assistant.assigned_timer
            )
        except StopIteration as error:
            raise ValueError(
                f"Assigned timer for {type(assistant).__name__} "
                "is not in its account category."
            ) from error
        record["assigned_timer"] = {
            "index": timer_index,
            "name": assistant.assigned_timer.name,
        }
    return record


def _serialize_timed_boost(boost: TimedBoost) -> dict:
    return {"active": boost.active, "cooldown": max(0, boost.cooldown)}


def save_accounts(
    accounts: List[Account],
    file_path: Optional[Union[str, Path]] = None,
) -> None:
    """Persist countdown durations and a Unix timestamp for offline catch-up."""
    path = Path(file_path) if file_path is not None else Path(__file__).with_name("data.json")
    now = time.time()
    records = []
    for account in accounts:
        home_building = [
            timer
            for timer in account.timers
            if timer.village == "Home Village" and timer.category == "Building"
        ]
        home_lab = [
            timer
            for timer in account.timers
            if timer.village == "Home Village" and timer.category == "Lab"
        ]
        home_pet = [
            timer
            for timer in account.timers
            if timer.village == "Home Village" and timer.category == "Pet"
        ]
        builder_building = [
            timer
            for timer in account.timers
            if timer.village == "Builder Base" and timer.category == "Building"
        ]
        builder_lab = [
            timer
            for timer in account.timers
            if timer.village == "Builder Base" and timer.category == "Lab"
        ]

        record = {
            "name": account.name,
            "saved_at": now,
            "Home Village": {
                "Building": {
                    "timers": [
                        _serialize_timer(timer) for timer in home_building
                    ],
                    "builder_apprentice": _serialize_assistant(
                        account.builder_apprentice, home_building
                    ),
                    "builder_potion": _serialize_timed_boost(
                        account.builder_potion
                    ),
                    "builder_bite": _serialize_timed_boost(account.builder_bite),
                },
                "Lab": {
                    "timers": [_serialize_timer(timer) for timer in home_lab],
                    "lab_assistant": _serialize_assistant(
                        account.lab_assistant, home_lab
                    ),
                    "lab_potion": _serialize_timed_boost(account.lab_potion),
                    "study_soup": _serialize_timed_boost(account.study_soup),
                },
                "Pet": {
                    "timers": [_serialize_timer(timer) for timer in home_pet],
                    "pet_potion": _serialize_timed_boost(account.pet_potion),
                },
            },
            "Builder Base": {
                "clock_tower": {
                    "active": account.clock_tower.active,
                    "cooldown": max(0, account.clock_tower.cooldown),
                    "active_cooldown_minutes": account.clock_tower.active_cooldown_minutes,
                },
                "Building": {
                    "timers": [
                        _serialize_timer(timer) for timer in builder_building
                    ]
                },
                "Lab": {
                    "timers": [_serialize_timer(timer) for timer in builder_lab]
                },
            },
        }
        if account.tag is not None:
            record["tag"] = account.tag
        records.append(record)

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as data_file:
            temporary_path = Path(data_file.name)
            json.dump(records, data_file, indent=2, ensure_ascii=False)
            data_file.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import List, Optional, Tuple, Type, Union

DATA_FILE = "data.json"

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


@dataclass(frozen=True)
class AppSettings:
    low_power_mode: bool = False
    dark_mode: bool = False


def _default_data_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / DATA_FILE
    return Path(__file__).resolve().parent / DATA_FILE


def load_settings(
    file_path: Optional[Union[str, Path]] = None,
) -> AppSettings:
    path = Path(file_path) if file_path is not None else _default_data_path()
    try:
        with path.open("r", encoding="utf-8") as data_file:
            document = json.load(data_file)
    except FileNotFoundError:
        return AppSettings()

    if not isinstance(document, dict):
        return AppSettings()
    settings = document.get("settings")
    if settings is None:
        return AppSettings()
    if not isinstance(settings, dict):
        raise ValueError("The application settings must be an object.")

    low_power_mode = settings.get("low_power_mode", False)
    dark_mode = settings.get("dark_mode", False)
    if not isinstance(low_power_mode, bool) or not isinstance(dark_mode, bool):
        raise ValueError("Application settings must be boolean values.")
    return AppSettings(
        low_power_mode=low_power_mode,
        dark_mode=dark_mode,
    )



def _load_assistant(record: object, name: str, account_name: str):
    if not isinstance(record, dict):
        raise ValueError(f"{name} data for account {account_name!r} must be an object.")

    active = record.get("active", False)
    assigned = record.get("assigned", False)
    multiplier = record.get("multiplier", 1)
    if not isinstance(active, bool) or not isinstance(assigned, bool):
        raise ValueError(
            f"{name} active and assigned values for account {account_name!r} "
            "must be booleans."
        )
    if isinstance(multiplier, bool) or not isinstance(multiplier, int) or multiplier < 0:
        raise ValueError(
            f"{name} multiplier for account {account_name!r} "
            "must be a non-negative integer."
        )
    return active, assigned, multiplier


def _remaining_seconds(
    ends_at: object,
    helper_name: str,
    account_name: str,
    now: float,
    end_description: str = "end time",
) -> int:
    ends_at = _validated_end_timestamp(
        ends_at, helper_name, account_name, end_description
    )
    return max(0, math.ceil(ends_at - now))


def _validated_end_timestamp(
    ends_at: object,
    item_name: str,
    account_name: str,
    end_description: str = "end time",
) -> float:
    if (
        isinstance(ends_at, bool)
        or not isinstance(ends_at, (int, float))
        or not math.isfinite(ends_at)
        or ends_at < 0
    ):
        raise ValueError(
            f"{item_name} {end_description} for account {account_name!r} "
            "must be a non-negative timestamp."
        )
    return float(ends_at)


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
    saved_at: Optional[float],
    cycles_when_unassigned: bool = False,
) -> None:
    if "ends_at" not in record:
        helper.cooldown = 0
        return

    ends_at = record["ends_at"]
    ends_at = _validated_end_timestamp(ends_at, helper_name, account_name)
    helper.cooldown = _remaining_seconds(
        ends_at, helper_name, account_name, now
    )
    if ends_at <= now:
        if saved_at is not None and ends_at <= saved_at:
            return
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
    saved_at: Optional[float],
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
    helper = helper_type(active=active)
    _restore_helper_cooldown(
        helper,
        record,
        helper_name,
        account_name,
        now,
        saved_at,
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
        if account.clock_tower.recharge_cooldown > 0:
            ticks = min(ticks, account.clock_tower.recharge_cooldown)
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
                account.clock_tower.active = False
        if account.clock_tower.recharge_cooldown > 0:
            account.clock_tower.recharge_cooldown -= ticks

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
    path = Path(file_path) if file_path is not None else _default_data_path()

    try:
        with path.open("r", encoding="utf-8") as data_file:
            records = json.load(data_file)
    except FileNotFoundError:
        return []
    if isinstance(records, dict):
        if "accounts" not in records:
            raise ValueError("The timer data must contain an accounts list.")
        records = records["accounts"]
    return load_accounts_from_records(records)


def load_accounts_from_records(records: object) -> List[Account]:
    """Validate and load account records without writing them to a file."""
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

        reference_time = saved_at if saved_at is not None else exported_at
        simulation_seconds = (
            max(0, int(now - reference_time))
            if reference_time is not None
            else 0
        )
        state_time = reference_time if reference_time is not None else now

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
                active_cooldown_minutes = tower_record.get(
                    "active_cooldown_minutes", 30
                )
                if not isinstance(active, bool):
                    raise ValueError(
                        f"Clock Tower active value for account {name!r} must be a boolean."
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
                    active_cooldown_minutes=active_cooldown_minutes,
                )
                _restore_helper_cooldown(
                    clock_tower,
                    tower_record,
                    "Clock Tower",
                    name,
                    state_time,
                    reference_time,
                )
                if clock_tower.cooldown == 0:
                    clock_tower.active = False
                if "recharge_ends_at" in tower_record:
                    clock_tower.recharge_cooldown = _remaining_seconds(
                        tower_record["recharge_ends_at"],
                        "Clock Tower recharge",
                        name,
                        state_time,
                        "end time",
                    )
                else:
                    clock_tower.recharge_cooldown = 0

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
                        state_time,
                        reference_time,
                    )
                    builder_bite = _load_timed_boost(
                        category_record.get("builder_bite", {}),
                        "Builder Bite",
                        BuilderBite,
                        name,
                        state_time,
                        reference_time,
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
                        state_time,
                        reference_time,
                    )
                    study_soup = _load_timed_boost(
                        category_record.get("study_soup", {}),
                        "Study Soup",
                        StudySoup,
                        name,
                        state_time,
                        reference_time,
                    )
                elif village == "Home Village" and category == "Pet":
                    if isinstance(category_record, dict):
                        timer_records = category_record.get("timers")
                        pet_potion = _load_timed_boost(
                            category_record.get("pet_potion", {}),
                            "Pet Potion",
                            PetPotion,
                            name,
                            state_time,
                            reference_time,
                        )
                    else:
                        timer_records = category_record
                elif village == "Builder Base" and isinstance(category_record, dict):
                    timer_records = category_record.get("timers")
                else:
                    timer_records = category_record

                if helper_name is not None and helper_type is not None:
                    values = _load_assistant(helper_record, helper_name, name)
                    active, assigned, multiplier = values
                    helper = helper_type(
                        active=active,
                        assigned=assigned,
                        multiplier=multiplier,
                    )
                    _restore_helper_cooldown(
                        helper,
                        helper_record,
                        helper_name,
                        name,
                        state_time,
                        reference_time,
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
                    if not isinstance(timer_name, str) or not timer_name.strip():
                        raise ValueError(
                            f"Timer at index {timer_index} in {village!r} / "
                            f"{category} for account {name!r} must have a non-empty name."
                        )
                    if "end_at" in timer_record or "ends_at" in timer_record:
                        ends_at = timer_record.get(
                            "end_at", timer_record.get("ends_at")
                        )
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
                        if reference_time is not None:
                            remaining = max(0, math.ceil(ends_at - reference_time))
                        else:
                            remaining = max(0, math.ceil(ends_at - now))
                    else:
                        raise ValueError(
                            f"Timer {timer_name!r} in {village!r} / {category} "
                            f"for account {name!r} must have an end timestamp."
                        )

                    timer = Timer(
                        name=timer_name,
                        value=remaining,
                        village=village,
                        category=category,
                    )
                    if reference_time is not None:
                        timer.end_at = ends_at
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
        if reference_time is not None:
            _simulate_elapsed(account, simulation_seconds)
        accounts.append(account)

    return accounts


def synchronize_accounts_from_saved_end_times(
    accounts: List[Account],
    file_path: Optional[Union[str, Path]] = None,
) -> int:
    """Advance all account state by shared timer drift from the saved data."""
    path = Path(file_path) if file_path is not None else _default_data_path()
    try:
        with path.open("r", encoding="utf-8") as data_file:
            document = json.load(data_file)
    except FileNotFoundError:
        return 0

    records = document.get("accounts") if isinstance(document, dict) else document
    if not isinstance(records, list):
        raise ValueError("The timer data must contain a list of accounts.")
    if len(records) != len(accounts):
        return 0

    now = time.time()
    drifts: List[float] = []
    timer_groups = (
        ("Home Village", "Building"),
        ("Home Village", "Lab"),
        ("Home Village", "Pet"),
        ("Builder Base", "Building"),
        ("Builder Base", "Lab"),
    )
    for account, record in zip(accounts, records):
        if not isinstance(record, dict):
            raise ValueError("Saved account data must contain objects.")
        if record.get("name") != account.name or record.get("tag") != account.tag:
            return 0

        grouped_timers = {
            group: [
                timer
                for timer in account.timers
                if timer.village == group[0] and timer.category == group[1]
            ]
            for group in timer_groups
        }
        if sum(map(len, grouped_timers.values())) != len(account.timers):
            return 0

        for village, category in timer_groups:
            village_record = record.get(village)
            if not isinstance(village_record, dict):
                raise ValueError(f"Saved account {account.name!r} has invalid village data.")
            category_record = village_record.get(category)
            timer_records = (
                category_record.get("timers")
                if isinstance(category_record, dict)
                else category_record
            )
            timers = grouped_timers[(village, category)]
            if not isinstance(timer_records, list):
                raise ValueError(
                    f"Saved timer data for {village!r} / {category} "
                    f"for account {account.name!r} must be a list."
                )
            if len(timer_records) != len(timers):
                return 0
            for timer, timer_record in zip(timers, timer_records):
                if not isinstance(timer_record, dict):
                    raise ValueError("Saved timer data must contain objects.")
                if timer_record.get("name") != timer.name:
                    return 0
                if timer.actual_time_left <= 0:
                    continue
                saved_end = timer_record.get(
                    "end_at", timer_record.get("ends_at")
                )
                if saved_end is None:
                    return 0
                saved_end = _validated_end_timestamp(
                    saved_end, timer.name, account.name
                )
                drifts.append(timer.end_at - saved_end)

        helper_records = (
            (
                account.builder_apprentice,
                record.get("Home Village", {}).get("Building", {}).get(
                    "builder_apprentice"
                ),
                "Builder Apprentice",
                "ends_at",
            ),
            (
                account.lab_assistant,
                record.get("Home Village", {}).get("Lab", {}).get(
                    "lab_assistant"
                ),
                "Lab Assistant",
                "ends_at",
            ),
            (
                account.builder_potion,
                record.get("Home Village", {}).get("Building", {}).get(
                    "builder_potion"
                ),
                "Builder Potion",
                "ends_at",
            ),
            (
                account.builder_bite,
                record.get("Home Village", {}).get("Building", {}).get(
                    "builder_bite"
                ),
                "Builder Bite",
                "ends_at",
            ),
            (
                account.lab_potion,
                record.get("Home Village", {}).get("Lab", {}).get("lab_potion"),
                "Lab Potion",
                "ends_at",
            ),
            (
                account.study_soup,
                record.get("Home Village", {}).get("Lab", {}).get("study_soup"),
                "Study Soup",
                "ends_at",
            ),
            (
                account.pet_potion,
                record.get("Home Village", {}).get("Pet", {}).get("pet_potion"),
                "Pet Potion",
                "ends_at",
            ),
            (
                account.clock_tower,
                record.get("Builder Base", {}).get("clock_tower"),
                "Clock Tower",
                "ends_at",
            ),
            (
                account.clock_tower,
                record.get("Builder Base", {}).get("clock_tower"),
                "Clock Tower recharge",
                "recharge_ends_at",
            ),
        )
        for helper, helper_record, helper_name, end_field in helper_records:
            cooldown = (
                helper.recharge_cooldown
                if end_field == "recharge_ends_at"
                else helper.cooldown
            )
            if cooldown <= 0:
                continue
            if not isinstance(helper_record, dict):
                return 0
            saved_end = helper_record.get(end_field)
            if saved_end is None:
                return 0
            saved_end = _validated_end_timestamp(
                saved_end, helper_name, account.name
            )
            drifts.append(now + cooldown - saved_end)

    if not drifts:
        return 0
    minimum_drift = min(drifts)
    if minimum_drift <= 3:
        return 0

    elapsed_seconds = math.floor(minimum_drift)
    if elapsed_seconds <= 0:
        return 0
    for account in accounts:
        _simulate_elapsed(account, elapsed_seconds)
    return elapsed_seconds


def _serialize_timer(timer: Timer) -> dict:
    return {
        "name": timer.name,
        "end_at": timer.end_at,
    }


def _serialize_assistant(
    assistant: Assistant,
    category_timers: List[Timer],
    saved_at: float,
) -> dict:
    record = {
        "active": assistant.active,
        "assigned": assistant.assigned,
        "ends_at": saved_at + max(0, assistant.cooldown),
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


def _serialize_timed_boost(boost: TimedBoost, saved_at: float) -> dict:
    return {
        "active": boost.active,
        "ends_at": saved_at + max(0, boost.cooldown),
    }


def save_accounts(
    accounts: List[Account],
    file_path: Optional[Union[str, Path]] = None,
    settings: Optional[AppSettings] = None,
) -> None:
    """Persist countdowns, application settings, and offline catch-up data."""
    path = Path(file_path) if file_path is not None else _default_data_path()
    if settings is None:
        settings = load_settings(path)
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
                    "timers": [_serialize_timer(timer) for timer in home_building],
                    "builder_apprentice": _serialize_assistant(
                        account.builder_apprentice, home_building, now
                    ),
                    "builder_potion": _serialize_timed_boost(
                        account.builder_potion, now
                    ),
                    "builder_bite": _serialize_timed_boost(
                        account.builder_bite, now
                    ),
                },
                "Lab": {
                    "timers": [_serialize_timer(timer) for timer in home_lab],
                    "lab_assistant": _serialize_assistant(
                        account.lab_assistant, home_lab, now
                    ),
                    "lab_potion": _serialize_timed_boost(
                        account.lab_potion, now
                    ),
                    "study_soup": _serialize_timed_boost(
                        account.study_soup, now
                    ),
                },
                "Pet": {
                    "timers": [_serialize_timer(timer) for timer in home_pet],
                    "pet_potion": _serialize_timed_boost(
                        account.pet_potion, now
                    ),
                },
            },
            "Builder Base": {
                "clock_tower": {
                    "active": account.clock_tower.active,
                    "ends_at": now + max(0, account.clock_tower.cooldown),
                    "recharge_ends_at": now
                    + max(0, account.clock_tower.recharge_cooldown),
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
            json.dump(
                {
                    "accounts": records,
                    "settings": {
                        "low_power_mode": settings.low_power_mode,
                        "dark_mode": settings.dark_mode,
                    },
                },
                data_file,
                indent=2,
                ensure_ascii=False,
            )
            data_file.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
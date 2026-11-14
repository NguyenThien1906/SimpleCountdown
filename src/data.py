import json
from pathlib import Path
from typing import List, Optional, Union

from assets import (
    Account,
    BuilderApprentice,
    BuilderPotion,
    ClockTower,
    LabPotion,
    LabAssistant,
    PetPotion,
    SUBCATEGORIES,
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


def _load_builder_potion(record: object, account_name: str) -> BuilderPotion:
    if not isinstance(record, dict):
        raise ValueError(
            f"Builder Potion data for account {account_name!r} must be an object."
        )

    active = record.get("active", False)
    cooldown = record.get("cooldown", 0)
    if not isinstance(active, bool):
        raise ValueError(
            f"Builder Potion active value for account {account_name!r} "
            "must be a boolean."
        )
    if isinstance(cooldown, bool) or not isinstance(cooldown, int) or cooldown < 0:
        raise ValueError(
            f"Builder Potion cooldown for account {account_name!r} "
            "must be a non-negative integer."
        )
    return BuilderPotion(active=active, cooldown=cooldown)


def _load_lab_potion(record: object, account_name: str) -> LabPotion:
    if not isinstance(record, dict):
        raise ValueError(
            f"Lab Potion data for account {account_name!r} must be an object."
        )

    active = record.get("active", False)
    cooldown = record.get("cooldown", 0)
    if not isinstance(active, bool):
        raise ValueError(
            f"Lab Potion active value for account {account_name!r} "
            "must be a boolean."
        )
    if isinstance(cooldown, bool) or not isinstance(cooldown, int) or cooldown < 0:
        raise ValueError(
            f"Lab Potion cooldown for account {account_name!r} "
            "must be a non-negative integer."
        )
    return LabPotion(active=active, cooldown=cooldown)


def _load_pet_potion(record: object, account_name: str) -> PetPotion:
    if not isinstance(record, dict):
        raise ValueError(
            f"Pet Potion data for account {account_name!r} must be an object."
        )

    active = record.get("active", False)
    cooldown = record.get("cooldown", 0)
    if not isinstance(active, bool):
        raise ValueError(
            f"Pet Potion active value for account {account_name!r} "
            "must be a boolean."
        )
    if isinstance(cooldown, bool) or not isinstance(cooldown, int) or cooldown < 0:
        raise ValueError(
            f"Pet Potion cooldown for account {account_name!r} "
            "must be a non-negative integer."
        )
    return PetPotion(active=active, cooldown=cooldown)


def load_accounts(file_path: Optional[Union[str, Path]] = None) -> List[Account]:
    path = Path(file_path) if file_path is not None else Path(__file__).with_name("data.json")

    with path.open("r", encoding="utf-8") as data_file:
        records = json.load(data_file)

    if not isinstance(records, list):
        raise ValueError("The timer data must contain a list of accounts.")

    accounts: List[Account] = []
    for account_index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"Account at index {account_index} must be an object.")

        name = record.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Account at index {account_index} must have a non-empty name.")

        timers: List[Timer] = []
        builder_apprentice = BuilderApprentice()
        lab_assistant = LabAssistant()
        clock_tower = ClockTower()
        builder_potion = BuilderPotion()
        lab_potion = LabPotion()
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

            for category in SUBCATEGORIES[village]:
                category_record = village_record.get(category)
                helper_name = None
                helper_type = None
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
                    builder_potion = _load_builder_potion(
                        category_record.get("builder_potion", {}),
                        name,
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
                    lab_potion = _load_lab_potion(
                        category_record.get("lab_potion", {}),
                        name,
                    )
                elif village == "Home Village" and category == "Pet":
                    if isinstance(category_record, dict):
                        timer_records = category_record.get("timers")
                        pet_potion = _load_pet_potion(
                            category_record.get("pet_potion", {}),
                            name,
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
                    if helper_type is BuilderApprentice:
                        builder_apprentice = helper
                    else:
                        lab_assistant = helper

                if not isinstance(timer_records, list):
                    raise ValueError(
                        f"Account {name!r} must have a list of timers "
                        f"for {village!r} / {category}."
                    )

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
                    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                        raise ValueError(
                            f"Timer {timer_name!r} in {village!r} / {category} "
                            f"for account {name!r} must have a non-negative "
                            "integer value in seconds."
                        )

                    timers.append(
                        Timer(
                            name=timer_name,
                            value=value,
                            village=village,
                            category=category,
                        )
                    )

        accounts.append(
            Account(
                name=name,
                timers=timers,
                builder_apprentice=builder_apprentice,
                lab_assistant=lab_assistant,
                clock_tower=clock_tower,
                builder_potion=builder_potion,
                lab_potion=lab_potion,
                pet_potion=pet_potion,
            )
        )

    return accounts
"""Translate Clash of Clans village export data IDs to display names.

Names are sourced from public game-data catalogs. The official Clash API does
not publish this game-data ID catalog.
"""

import json
import os
import re
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def _load_data_id_to_name() -> Dict[int, str]:
    if getattr(sys, "frozen", False):
        path = Path(sys.executable).resolve().parent / "data_id.json"
    else:
        path = Path(__file__).with_name("data_id.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("data_id.json must contain an object mapping IDs to names.")

    translated: Dict[int, str] = {}
    for raw_id, name in data.items():
        if not isinstance(raw_id, str) or not raw_id.isdecimal():
            raise ValueError(f"Invalid data ID {raw_id!r} in data_id.json.")
        data_id = int(raw_id)
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Name for data ID {raw_id!r} must be a non-empty string.")
        if data_id in translated:
            raise ValueError(f"Duplicate data ID {raw_id!r} in data_id.json.")
        translated[data_id] = name
    return translated


DATA_ID_TO_NAME = _load_data_id_to_name()


def translate_data_ids(value: Any) -> Any:
    """Return a copy of JSON-like data with numeric ``data`` IDs replaced."""
    if isinstance(value, dict):
        translated = {}
        for key, item in value.items():
            if key == "data" and isinstance(item, int) and not isinstance(item, bool):
                try:
                    translated[key] = DATA_ID_TO_NAME[item]
                except KeyError as error:
                    raise ValueError(f"Unknown Clash of Clans data ID: {item}") from error
            else:
                translated[key] = translate_data_ids(item)
        return translated
    if isinstance(value, list):
        return [translate_data_ids(item) for item in value]
    return value


def translate_village_data(
    file_path: Union[str, Path] = "raw_village_data.json",
) -> Any:
    """Load a village JSON file and translate its data IDs."""
    data = _load_raw_village_data(file_path)
    return translate_data_ids(data)


_TIMER_GROUPS: Dict[Tuple[str, str], Tuple[str, ...]] = {
    ("Home Village", "Building"): ("buildings", "heroes", "traps", "guardians"),
    ("Home Village", "Lab"): ("units", "siege_machines", "spells"),
    ("Home Village", "Pet"): ("pets",),
    ("Builder Base", "Building"): ("buildings2", "traps2", "heroes2"),
    ("Builder Base", "Lab"): ("units2",),
}
_BUILDER_APPRENTICE_ID = 93000000
_LAB_ASSISTANT_ID = 93000001
_CLOCK_TOWER_ID = 1000039


def get_player_name(player_tag: str, api_token: Optional[str] = None) -> str:
    """Look up a player's display name, falling back to their tag if unavailable."""
    if not isinstance(player_tag, str) or not player_tag.strip():
        raise ValueError("Player tag must be a non-empty string.")
    player_tag = player_tag.strip()
    token = api_token or os.environ.get("COC_API_TOKEN")
    if not token:
        return player_tag

    url = f"https://api.clashofclans.com/v1/players/{quote(player_tag, safe='')}"
    request = Request(
        url,
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            player = json.load(response)
    except HTTPError as error:
        if error.code in (400, 404):
            return player_tag
        raise RuntimeError(
            f"Clash of Clans API player lookup failed with HTTP {error.code}."
        ) from error
    except URLError as error:
        raise RuntimeError(f"Clash of Clans API request failed: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError("Clash of Clans API returned invalid JSON.") from error

    name = player.get("name") if isinstance(player, dict) else None
    if not isinstance(name, str) or not name.strip():
        raise RuntimeError("Clash of Clans API response did not contain a player name.")
    return name


def _load_raw_village_data(file_path: Union[str, Path]) -> Dict[str, Any]:
    path = Path(file_path)
    if not path.is_absolute():
        path = Path(__file__).parent / path
    return _parse_raw_village_data(path.read_text(encoding="utf-8"))


def _parse_raw_village_data(raw_text: str) -> Dict[str, Any]:
    # Normalize the malformed Town Hall ID in memory; keep the source untouched.
    corrected_text = re.sub(
        r'("data"\s*:\s*)(?:00000001|10000001)\b',
        r"\g<1>1000001",
        raw_text,
    )
    data = json.loads(corrected_text)
    if not isinstance(data, dict):
        raise ValueError("The village export must contain a JSON object.")
    return data


def _timer_records(
    village_data: Dict[str, Any],
    record_groups: Tuple[str, ...],
    category: str,
    exported_at: int,
) -> List[Dict[str, Union[str, int, float]]]:
    timers: List[Dict[str, Union[str, int, float]]] = []
    for group in record_groups:
        records = village_data.get(group, [])
        if not isinstance(records, list):
            raise ValueError(f"Village export field {group!r} must contain a list.")
        for index, record in enumerate(records):
            if not isinstance(record, dict) or "timer" not in record:
                continue
            data_id = record.get("data")
            if isinstance(data_id, bool) or not isinstance(data_id, int):
                raise ValueError(
                    f"Record {index} in {group!r} must have an integer data ID."
                )
            try:
                name = DATA_ID_TO_NAME[data_id]
            except KeyError as error:
                raise ValueError(
                    f"Unknown Clash of Clans data ID {data_id} in {group!r}."
                ) from error
            seconds = record["timer"]
            if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds < 0:
                raise ValueError(
                    f"Timer for {name!r} in {group!r} must be a non-negative "
                    "integer number of seconds."
                )
            if category == "Lab":
                name = f"{name} Research"
            timers.append({"name": name, "end_at": exported_at + seconds})
    return timers


def _assigned_timer(
    village_data: Dict[str, Any],
    record_groups: Tuple[str, ...],
) -> Optional[Dict[str, Any]]:
    matches: List[Dict[str, Union[int, str]]] = []
    category_timer_index = 0
    for group in record_groups:
        records = village_data.get(group, [])
        if not isinstance(records, list):
            raise ValueError(f"Village export field {group!r} must contain a list.")
        for record in records:
            if not isinstance(record, dict) or "timer" not in record:
                continue
            if record.get("helper_recurrent") is True:
                data_id = record.get("data")
                if isinstance(data_id, bool) or not isinstance(data_id, int):
                    raise ValueError(
                        f"Assigned helper record in {group!r} must have an integer data ID."
                    )
                try:
                    name = DATA_ID_TO_NAME[data_id]
                except KeyError as error:
                    raise ValueError(
                        f"Unknown Clash of Clans data ID {data_id} in {group!r}."
                    ) from error
                if group in ("units", "siege_machines", "spells", "units2"):
                    name = f"{name} Research"
                matches.append({"index": category_timer_index, "name": name})
            category_timer_index += 1

    if len(matches) > 1:
        raise ValueError("Multiple timers are marked as assigned to the same helper.")
    return matches[0] if matches else None


def _assistant_settings(
    village_data: Dict[str, Any],
    helper_id: int,
    assigned_timer: Optional[Dict[str, Any]],
    exported_at: int,
) -> Dict[str, Any]:
    records = village_data.get("helpers", [])
    if not isinstance(records, list):
        raise ValueError("Village export field 'helpers' must contain a list.")
    helper_record: Optional[Dict[str, Any]] = next(
        (
            record
            for record in records
            if isinstance(record, dict) and record.get("data") == helper_id
        ),
        None,
    )
    if helper_record is None:
        return {
            "active": False,
            "assigned": False,
            "ends_at": exported_at,
            "multiplier": 1,
        }

    level = helper_record.get("lvl")
    cooldown = helper_record.get("helper_cooldown", 0)
    if isinstance(level, bool) or not isinstance(level, int) or level < 0:
        raise ValueError(f"Helper {helper_id} must have a non-negative integer level.")
    if isinstance(cooldown, bool) or not isinstance(cooldown, int) or cooldown < 0:
        raise ValueError(
            f"Helper {helper_id} cooldown must be a non-negative integer."
        )
    return {
        "active": 0 < cooldown <= 60 * 60,
        "assigned": assigned_timer is not None,
        "ends_at": exported_at + cooldown,
        "multiplier": level,
        **({"assigned_timer": assigned_timer} if assigned_timer is not None else {}),
    }


def extract_timers(
    file_path: Union[str, Path] = "raw_village_data.json",
) -> List[Dict[str, Any]]:
    """Convert village timers into timestamp-based data.json records."""
    return extract_timers_from_data(_load_raw_village_data(file_path))


def extract_timers_from_json(raw_text: str) -> List[Dict[str, Any]]:
    """Translate a pasted village export into data.json-compatible records."""
    return extract_timers_from_data(_parse_raw_village_data(raw_text))


def extract_timers_from_data(
    village_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Convert parsed village data into timestamp-based account records."""
    tag = village_data.get("tag")
    if not isinstance(tag, str) or not tag.strip():
        raise ValueError("The village export must contain a non-empty account tag.")

    exported_at = village_data.get("timestamp")
    if isinstance(exported_at, bool) or not isinstance(exported_at, int) or exported_at < 0:
        raise ValueError("The village export must contain a non-negative integer timestamp.")

    groups = {
        key: _timer_records(village_data, source_groups, key[1], exported_at)
        for key, source_groups in _TIMER_GROUPS.items()
    }
    assigned_timers = {
        _BUILDER_APPRENTICE_ID: _assigned_timer(
            village_data, _TIMER_GROUPS[("Home Village", "Building")]
        ),
        _LAB_ASSISTANT_ID: _assigned_timer(
            village_data, _TIMER_GROUPS[("Home Village", "Lab")]
        ),
    }
    builder_buildings = village_data.get("buildings2", [])
    if not isinstance(builder_buildings, list):
        raise ValueError("Village export field 'buildings2' must contain a list.")
    clock_tower_level = next(
        (
            record.get("lvl")
            for record in builder_buildings
            if isinstance(record, dict) and record.get("data") == _CLOCK_TOWER_ID
        ),
        1,
    )
    if (
        isinstance(clock_tower_level, bool)
        or not isinstance(clock_tower_level, int)
        or clock_tower_level < 1
    ):
        raise ValueError("Clock Tower level must be a positive integer.")
    boosts = village_data.get("boosts", {})
    if not isinstance(boosts, dict):
        raise ValueError("Village export field 'boosts' must contain an object.")
    lab_boost = boosts.get("lab_boost", 0)
    builder_bite_duration = boosts.get("builder_consumable", 0)
    clock_tower_boost = boosts.get("clocktower_boost", 0)
    clock_tower_cooldown = boosts.get("clocktower_cooldown", 0)
    for field, value in (
        ("lab_boost", lab_boost),
        ("builder_consumable", builder_bite_duration),
        ("clocktower_boost", clock_tower_boost),
        ("clocktower_cooldown", clock_tower_cooldown),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(
                f"Village export boost {field!r} must be a non-negative integer."
            )
    player_name = get_player_name(tag)
    return [
        {
            "name": player_name,
            "tag": tag,
            "saved_at": exported_at,
            "Home Village": {
                "Building": {
                    "timers": groups[("Home Village", "Building")],
                    "builder_apprentice": _assistant_settings(
                        village_data,
                        _BUILDER_APPRENTICE_ID,
                        assigned_timers[_BUILDER_APPRENTICE_ID],
                        exported_at,
                    ),
                    "builder_potion": {
                        "active": False,
                        "ends_at": exported_at,
                    },
                    "builder_bite": {
                        "active": builder_bite_duration > 0,
                        "ends_at": exported_at + builder_bite_duration,
                    },
                },
                "Lab": {
                    "timers": groups[("Home Village", "Lab")],
                    "lab_assistant": _assistant_settings(
                        village_data,
                        _LAB_ASSISTANT_ID,
                        assigned_timers[_LAB_ASSISTANT_ID],
                        exported_at,
                    ),
                    "lab_potion": {
                        "active": lab_boost > 0,
                        "ends_at": exported_at + lab_boost,
                    },
                    "study_soup": {
                        "active": False,
                        "ends_at": exported_at,
                    },
                },
                "Pet": {
                    "timers": groups[("Home Village", "Pet")],
                    "pet_potion": {"active": False, "ends_at": exported_at},
                },
            },
            "Builder Base": {
                "clock_tower": {
                    "active": clock_tower_boost > 0,
                    "ends_at": exported_at + clock_tower_boost,
                    "recharge_ends_at": exported_at + clock_tower_cooldown,
                    "active_cooldown_minutes": 12 + 2 * clock_tower_level,
                },
                "Building": groups[("Builder Base", "Building")],
                "Lab": groups[("Builder Base", "Lab")],
            },
        }
    ]


def write_data_json(
    output_path: Union[str, Path],
    file_path: Union[str, Path] = "raw_village_data.json",
) -> None:
    """Write extracted timers as a data.json-compatible account list."""
    path = Path(output_path)
    path.write_text(
        json.dumps(extract_timers(file_path), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract Clash of Clans village timers into data.json format.",
        epilog=(
            "Set the COC_API_TOKEN environment variable to look up the player's "
            "name using the official Clash of Clans API."
        ),
    )
    parser.add_argument(
        "output_path",
        help="Path to write the extracted account data.",
    )
    arguments = parser.parse_args()
    write_data_json(arguments.output_path)
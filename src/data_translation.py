"""Translate Clash of Clans village export data IDs to display names.

Names are sourced from public game-data catalogs. The official Clash API does
not publish this game-data ID catalog.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DATA_ID_TO_NAME: Dict[int, str] = {
    1000000: "Army Camp",
    1000001: "Town Hall",
    1000002: "Elixir Collector",
    1000003: "Elixir Storage",
    1000004: "Gold Mine",
    1000005: "Gold Storage",
    1000006: "Barracks",
    1000007: "Laboratory",
    1000008: "Cannon",
    1000009: "Archer Tower",
    1000010: "Wall",
    1000011: "Wizard Tower",
    1000012: "Air Defense",
    1000013: "Mortar",
    1000014: "Clan Castle",
    1000015: "Builder's Hut",
    1000019: "Hidden Tesla",
    1000020: "Spell Factory",
    1000021: "X-Bow",
    1000023: "Dark Elixir Drill",
    1000024: "Dark Elixir Storage",
    1000026: "Dark Barracks",
    1000027: "Inferno Tower",
    1000028: "Air Sweeper",
    1000029: "Dark Spell Factory",
    1000032: "Bomb Tower",
    1000033: "Wall",
    1000034: "Builder Hall",
    1000035: "Elixir Collector",
    1000036: "Elixir Storage",
    1000037: "Gold Mine",
    1000038: "Gold Storage",
    1000039: "Clock Tower",
    1000040: "Builder Barracks",
    1000041: "Double Cannon",
    1000042: "Army Camp",
    1000043: "Hidden Tesla",
    1000044: "Cannon",
    1000045: "Multi Mortar",
    1000046: "Star Laboratory",
    1000048: "Archer Tower",
    1000049: "Reinforcement Camp",
    1000050: "Firecrackers",
    1000051: "Guard Post",
    1000053: "Battle Machine Altar",
    1000054: "Air Bombs",
    1000055: "Crusher",
    1000056: "Roaster",
    1000058: "Gem Mine",
    1000059: "Workshop",
    1000067: "Scattershot",
    1000068: "Pet House",
    1000070: "Blacksmith",
    1000071: "Hero Hall",
    1000072: "Spell Tower",
    1000077: "Monolith",
    1000078: "O.T.T.O's Outpost",
    1000082: "Healing Hut",
    1000084: "Multi-Archer Tower",
    1000085: "Ricochet Cannon",
    1000089: "Firespitter",
    1000093: "Helper Hut",
    1000097: "Crafting Station",
    4000000: "Barbarian",
    4000001: "Archer",
    4000002: "Goblin",
    4000003: "Giant",
    4000004: "Wall Breaker",
    4000005: "Balloon",
    4000006: "Wizard",
    4000007: "Healer",
    4000008: "Dragon",
    4000009: "P.E.K.K.A",
    4000010: "Minion",
    4000011: "Hog Rider",
    4000012: "Valkyrie",
    4000013: "Golem",
    4000015: "Witch",
    4000017: "Lava Hound",
    4000022: "Bowler",
    4000023: "Baby Dragon",
    4000024: "Miner",
    4000031: "Raged Barbarian",
    4000032: "Sneaky Archer",
    4000033: "Beta Minion",
    4000034: "Boxer Giant",
    4000035: "Bomber",
    4000037: "Cannon Cart",
    4000041: "Baby Dragon",
    4000042: "Night Witch",
    4000051: "Wall Wrecker",
    4000052: "Battle Blimp",
    4000053: "Yeti",
    4000058: "Ice Golem",
    4000059: "Electro Dragon",
    4000062: "Stone Slammer",
    4000065: "Dragon Rider",
    4000075: "Siege Barracks",
    4000082: "Headhunter",
    4000087: "Log Launcher",
    4000095: "Electro Titan",
    4000097: "Apprentice Warden",
    4000109: "Ruin Witch",
    4000110: "Root Rider",
    4000123: "Druid",
    4000132: "Thrower",
    4000150: "Furnace",
    8000004: "Bush",
    8000008: "Mushroom",
    8000010: "Trunk",
    8000055: "Old Barbarian Statue",
    8000063: "Tall Grass",
    8000064: "Tall Grass",
    8000091: "Root",
    8000092: "Large Root",
    12000000: "Bomb",
    12000001: "Spring Trap",
    12000002: "Giant Bomb",
    12000005: "Air Bomb",
    12000006: "Seeking Air Mine",
    12000008: "Skeleton Trap",
    12000010: "Spring Trap",
    12000011: "Push Trap",
    12000013: "Mine",
    12000014: "Mega Mine",
    12000016: "Tornado Trap",
    18000065: "Logmas Tree",
    18000069: "Wizard Statue",
    18000070: "Goblin King Tribute",
    18000115: "Gingerbread Bakery",
    18000141: "Wizard Vendor",
    18000172: "Rumbling Goblins",
    18000173: "Golden Giant",
    18000175: "Surprise Wheel",
    18000239: "Bro Force",
    18000248: "Unknown decoration (18000248)",
    26000000: "Lightning Spell",
    26000001: "Healing Spell",
    26000002: "Rage Spell",
    26000003: "Jump Spell",
    26000005: "Freeze Spell",
    26000009: "Poison Spell",
    26000010: "Earthquake Spell",
    26000011: "Haste Spell",
    26000016: "Clone Spell",
    26000017: "Skeleton Spell",
    26000028: "Bat Spell",
    26000035: "Invisibility Spell",
    26000053: "Recall Spell",
    26000070: "Overgrowth Spell",
    26000098: "Revive Spell",
    26000120: "Totem Spell",
    28000000: "Barbarian King",
    28000001: "Archer Queen",
    28000002: "Grand Warden",
    28000003: "Battle Machine",
    28000004: "Royal Champion",
    28000005: "Battle Copter",
    28000006: "Minion Prince",
    28000007: "Dragon Duke",
    73000000: "L.A.S.S.I",
    73000001: "Mighty Yak",
    73000002: "Electro Owl",
    73000003: "Unicorn",
    73000004: "Phoenix",
    73000007: "Poison Lizard",
    73000008: "Diggy",
    73000009: "Frosty",
    73000010: "Spirit Fox",
    73000011: "Angry Jelly",
    90000000: "Barbarian Puppet",
    90000001: "Rage Vial",
    90000002: "Archer Puppet",
    90000003: "Invisibility Vial",
    90000004: "Eternal Tome",
    90000005: "Life Gem",
    90000006: "Seeking Shield",
    90000007: "Royal Gem",
    90000008: "Earthquake Boots",
    90000009: "Hog Rider Puppet",
    90000010: "Giant Gauntlet",
    90000011: "Vampstache",
    90000012: "Haste Vial",
    90000013: "Rocket Spear",
    90000014: "Spiky Ball",
    90000015: "Frozen Arrow",
    90000016: "Electro Fangs",
    90000017: "Giant Arrow",
    90000019: "Heroic Torch",
    90000020: "Healer Puppet",
    90000022: "Fireball",
    90000024: "Rage Gem",
    90000032: "Snake Bracelet",
    90000034: "Healing Tome",
    90000035: "Dark Crown",
    90000039: "Magic Mirror",
    90000040: "Electro Boots",
    90000041: "Lavaloon Puppet",
    90000042: "Henchmen Puppet",
    90000043: "Dark Orb",
    90000044: "Metal Pants",
    90000047: "Noble Iron",
    90000048: "Action Figure",
    90000049: "Meteor Staff",
    90000050: "Frost Flake",
    90000051: "Stick Horse",
    90000052: "Fire Heart",
    90000053: "Rocket Backpack",
    90000056: "Stun Blaster",
    90000057: "Flame Blower",
    90000059: "Monolith Arrow",
    90000060: "Revenge Deck",
    90000061: "Portal Pendant",
    93000000: "Builder's Apprentice",
    93000001: "Lab Assistant",
    102000033: "Hitpoints",
    102000034: "Damage",
    102000035: "Seconds Active",
    102000036: "Hitpoints",
    102000037: "Damage",
    102000038: "Poison Level",
    102000039: "Hitpoints",
    102000040: "Damage",
    102000041: "Explosion Damage",
    103000011: "Hot Candle",
    103000012: "Hero Hunter",
    103000013: "Cake-A-Pult",
}


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
    ("Home Village", "Building"): ("buildings", "heroes", "traps"),
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
) -> List[Dict[str, Union[str, int]]]:
    timers: List[Dict[str, Union[str, int]]] = []
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
            timers.append({"name": name, "value": seconds})
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
            "cooldown": 0,
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
        "cooldown": cooldown,
        "multiplier": level,
        **({"assigned_timer": assigned_timer} if assigned_timer is not None else {}),
    }


def extract_timers(
    file_path: Union[str, Path] = "raw_village_data.json",
) -> List[Dict[str, Any]]:
    """Convert village timers into duration-based data.json records."""
    return extract_timers_from_data(_load_raw_village_data(file_path))


def extract_timers_from_json(raw_text: str) -> List[Dict[str, Any]]:
    """Translate a pasted village export into data.json-compatible records."""
    return extract_timers_from_data(_parse_raw_village_data(raw_text))


def extract_timers_from_data(
    village_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Convert parsed village data into duration-based account records."""
    tag = village_data.get("tag")
    if not isinstance(tag, str) or not tag.strip():
        raise ValueError("The village export must contain a non-empty account tag.")

    exported_at = village_data.get("timestamp")
    if isinstance(exported_at, bool) or not isinstance(exported_at, int) or exported_at < 0:
        raise ValueError("The village export must contain a non-negative integer timestamp.")

    groups = {
        key: _timer_records(village_data, source_groups, key[1])
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
                    ),
                    "builder_potion": {"active": False, "cooldown": 0},
                    "builder_bite": {"active": False, "cooldown": 0},
                },
                "Lab": {
                    "timers": groups[("Home Village", "Lab")],
                    "lab_assistant": _assistant_settings(
                        village_data,
                        _LAB_ASSISTANT_ID,
                        assigned_timers[_LAB_ASSISTANT_ID],
                    ),
                    "lab_potion": {"active": False, "cooldown": 0},
                    "study_soup": {"active": False, "cooldown": 0},
                },
                "Pet": {
                    "timers": groups[("Home Village", "Pet")],
                    "pet_potion": {"active": False, "cooldown": 0},
                },
            },
            "Builder Base": {
                "clock_tower": {
                    "active": False,
                    "cooldown": 0,
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
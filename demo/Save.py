#!/usr/bin/env python3
import json
import time
from typing import List, Dict, Any, Optional

DEFAULT_FILE = "save.json"

def split_timer_name(name: str, type_options: Optional[List[str]] = None):
    parts = str(name).split(" - ", 2)
    if len(parts) == 3:
        return parts[0].strip(), parts[1].strip(), parts[2].strip()
    if len(parts) == 2:
        name_part, upgrade = parts[0].strip(), parts[1].strip()
        for timer_type in type_options or []:
            suffix = f" ({timer_type})"
            if upgrade.endswith(suffix):
                return name_part, upgrade[:-len(suffix)].strip(), timer_type
        return name_part, upgrade, None
    return str(name).strip(), None, None

def load_state(filename: str = DEFAULT_FILE) -> Optional[Dict[str, Any]]:
    """
    Load saved application state from JSON.
    Returns a dict with name lists and timers, or None if no file / parse error.
    Timer names may use separate "name", "upgrade", and "type" fields or the legacy combined "name" field.
    The optional "disabled" and "note" fields default to false and an empty string.
    """
    try:
        with open(filename, "r", encoding="utf-8") as f:
            state = json.load(f)
        # Basic validation; keep the A/B keys so older saves load unchanged.
        if not isinstance(state, dict):
            return None
        state.setdefault("name_list_a", [])
        state.setdefault("name_list_b", [])
        state.setdefault("name_list_type", [])
        state.setdefault("timers", [])
        return state
    except FileNotFoundError:
        return None
    except Exception:
        # Best-effort: don't raise to caller
        return None

def save_state(name_list_a: List[str], name_list_b: List[str], timers: List[Any],
               filename: str = DEFAULT_FILE,
               name_list_type: Optional[List[str]] = None) -> None:
    """
    Save application state to JSON.
    timers: iterable of objects that expose a combined `name` and numeric `end_ts`.
    Timer names are stored as separate `name`, `upgrade`, and `type` fields, alongside timer state.
    """
    timers_state = []
    for t in timers:
        try:
            name, upgrade, timer_type = split_timer_name(
                getattr(t, "name", ""), name_list_type
            )
            timers_state.append({
                "name": name,
                "upgrade": upgrade,
                "type": timer_type,
                "end_ts": int(getattr(t, "end_ts", int(time.time()))),
                "disabled": bool(getattr(t, "disabled", False)),
                "note": str(getattr(t, "note", "")),
                "resource": str(getattr(t, "resource", "Empty!!!!!!!!!!!!!!!"))
            })
        except Exception:
            # skip non-serializable timer
            continue

    state = {
        "name_list_a": list(name_list_a),
        "name_list_b": list(name_list_b),
        "name_list_type": list(name_list_type or []),
        "timers": timers_state
    }

    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        # best-effort: swallow errors so shutdown is not blocked
        pass





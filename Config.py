import json, os, re

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Factors.json")

DEFAULT_DARK = 1.0
DEFAULT_LIGHT = 0.95

DETECT_TYPES = ["class", "name", "regex", "role"]


def _entry(detect: dict, dark=DEFAULT_DARK, light=DEFAULT_LIGHT) -> dict:
    return {"AppDetect": dict(detect), "Dark": float(dark), "Light": float(light)}


def normalize(data) -> list:
    """Accept the new list format or the legacy {"title substring": factor} dict."""
    entries = []
    if isinstance(data, dict):
        for sub, fac in data.items():
            entries.append(_entry({"name": sub}, DEFAULT_DARK, fac))
        return entries

    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        detect = {k: str(v) for k, v in dict(item.get("AppDetect", {})).items() if k in DETECT_TYPES}
        try:
            dark = float(item.get("Dark", DEFAULT_DARK))
            light = float(item.get("Light", DEFAULT_LIGHT))
        except (TypeError, ValueError):
            dark, light = DEFAULT_DARK, DEFAULT_LIGHT
        entries.append(_entry(detect, dark, light))
    return entries


def load(path: str = CONFIG_PATH) -> list:
    try:
        with open(path, "r") as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        print("Config load failed:", e)
        return []

    entries = normalize(raw)
    if isinstance(raw, dict):  # migrate legacy file
        save(entries, path)
    return entries


def save(entries: list, path: str = CONFIG_PATH):
    with open(path, "w") as f:
        json.dump(entries, f, indent=4)


def dumps(entries: list) -> str:
    return json.dumps(entries)


def matches(detect: dict, info: dict) -> bool:
    """All detection methods of an entry must match. Mirrors the KWin plugin."""
    if not detect:
        return False
    caption = info.get("name", "")
    for kind, pattern in detect.items():
        if kind == "class":
            if pattern.lower() not in info.get("class", "").lower().split():
                return False
        elif kind == "name":
            if pattern.lower() not in caption.lower():
                return False
        elif kind == "role":
            if pattern.lower() != info.get("role", "").lower():
                return False
        elif kind == "regex":
            try:
                if not re.search(pattern, caption, re.IGNORECASE):
                    return False
            except re.error:
                return False
        else:
            return False
    return True


def find_entry(entries: list, info: dict):
    for entry in entries:
        if matches(entry["AppDetect"], info):
            return entry
    return None


def light_factor(entries: list, info: dict) -> float:
    entry = find_entry(entries, info)
    return entry["Light"] if entry else DEFAULT_LIGHT

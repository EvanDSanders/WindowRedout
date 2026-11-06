import subprocess, re

# Title of the window that was focused last (used for idle exceptions)
name = ''
lastInfo = None

noIdles = {
    "YouTube": 0.0,
}


def _run(cmd: str) -> str:
    return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()


def getWindowInfo():
    """Info about the focused X11 window: {class, name, role}.

    Returns None when no window can be queried, which happens when the
    mouse leaves the screen via DeskFlow. Plasma itself is ignored.
    """
    global name, lastInfo

    try:
        wid = _run("xdotool getactivewindow")
        title = _run(f"xdotool getwindowname {wid}")
    except Exception as e:
        print("Error", e)
        name = ''
        return None

    try:
        prop = _run(f"xprop -id {wid} WM_CLASS WM_WINDOW_ROLE")
    except Exception:
        prop = ''

    cls = ''
    m = re.search(r'WM_CLASS\(STRING\) = "(.*)", "(.*)"', prop)
    if m:
        cls = f"{m.group(1)} {m.group(2)}"
    role = ''
    m = re.search(r'WM_WINDOW_ROLE\(STRING\) = "(.*)"', prop)
    if m:
        role = m.group(1)

    if title == "Plasma" and lastInfo:
        return lastInfo

    name = title
    lastInfo = {"class": cls, "name": title, "role": role}
    return lastInfo


def getIdle():
    for item, fac in noIdles.items():
        if item in name:
            return fac

    try:
        return int(_run("xprintidle"))
    except Exception as e:
        print("Error in Idle", e)
        return 0

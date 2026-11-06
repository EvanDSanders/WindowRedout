import json

from PySide6.QtDBus import QDBusConnection, QDBusInterface

SERVICE = "org.kde.KWin"
PATH = "/WindowRedout"
IFACE = "org.windowredout.Effect"
EFFECT_ID = "windowredout"


class KWinBridge:
    """DBus client for the WindowRedout KWin effect."""

    def __init__(self):
        self.bus = QDBusConnection.sessionBus()
        self.effect = QDBusInterface(SERVICE, PATH, IFACE, self.bus)
        self.effects = QDBusInterface(SERVICE, "/Effects", "org.kde.kwin.Effects", self.bus)
        self.compositor = QDBusInterface(SERVICE, "/Compositor", "org.kde.kwin.Compositing", self.bus)
        self.configJson = None
        self.lastState = None
        self.triedLoad = False

    def compositorRunning(self) -> bool:
        if not self.compositor.isValid():
            return False
        return bool(self.compositor.property("active"))

    def _ping(self) -> bool:
        if not self.effect.isValid():
            return False
        reply = self.effect.call("ping")
        return reply.arguments() != [] and reply.arguments()[0] is True

    def available(self) -> bool:
        """True when the compositor runs and the effect answers on DBus."""
        if not self.compositorRunning():
            self.triedLoad = False
            return False
        if self._ping():
            return True

        if not self.triedLoad and self.effects.isValid():
            self.triedLoad = True
            self.effects.call("loadEffect", EFFECT_ID)
            return self._ping()
        return False

    def reset(self):
        """Forget what was sent so the next push is a full resync."""
        self.configJson = None
        self.lastState = None

    def pushConfig(self, configJson: str):
        if configJson != self.configJson:
            self.effect.call("setConfig", configJson)
            self.configJson = configJson

    def pushState(self, baseTemp: float, idleT: float, allDim: bool):
        state = (round(baseTemp), round(idleT, 3), allDim)
        if state != self.lastState:
            self.effect.call("setState", float(baseTemp), float(idleT), bool(allDim))
            self.lastState = state

    def pushNeutral(self):
        """Stop the effect tinting windows (used while gamma ramps are active)."""
        if self.effect.isValid():
            self.effect.call("setState", 6500.0, 0.0, False)
        self.lastState = None

    def activeWindow(self):
        reply = self.effect.call("activeWindow")
        args = reply.arguments()
        if not args:
            return None
        try:
            info = json.loads(args[0])
        except (TypeError, ValueError):
            return None
        return info or None

    def unload(self):
        if self.effects.isValid():
            self.effects.call("unloadEffect", EFFECT_ID)

#!/bin/bash
# Builds the KWin effect, installs it (via pkexec) when out of date, then starts WindowRedout.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$DIR/KWin/windowredout"
BUILD="$SRC/build"
NAME="kwin_effect_windowredout.so"

PLUGIN_ROOT="$(qtpaths --plugin-dir 2>/dev/null || echo /usr/lib/x86_64-linux-gnu/qt5/plugins)"
INSTALLED="$PLUGIN_ROOT/kwin/effects/plugins/$NAME"

mkdir -p "$BUILD"
if [ ! -f "$BUILD/CMakeCache.txt" ]; then
    cmake -S "$SRC" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr || exit 1
fi
cmake --build "$BUILD" || { echo "KWin effect build failed"; exit 1; }

if ! cmp -s "$BUILD/$NAME" "$INSTALLED"; then
    echo "KWin effect missing or out of date, installing..."
    if pkexec cmake --install "$BUILD"; then
        # reload so KWin picks up the new plugin (a KWin restart may be needed if it was already loaded)
        qdbus org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect windowredout >/dev/null 2>&1
        qdbus org.kde.KWin /Effects org.kde.kwin.Effects.loadEffect windowredout >/dev/null 2>&1
    else
        echo "Install failed or cancelled; running without the KWin effect (gamma ramps)."
    fi
fi

cd "$DIR" || exit 1
exec /usr/bin/python3 WindowRedout.py "$@"

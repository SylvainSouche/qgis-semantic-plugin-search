#!/bin/sh
# Run the plugin inside real QGIS, headless (offscreen Qt platform).
# Supports the official 4.x bundles, the official 3.x bundles and the
# MacPorts QGIS3 bundle. Usage: QGIS_APP=/path/to/QGIS.app tools/RunQgisSmoke.sh
set -eu

APP_DIR="${QGIS_APP:-/Applications/QGIS-final-4_2_3.app}"
CONTENTS="$APP_DIR/Contents"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

# Official 4.x bundle: interpreter at MacOS/python3.12.
if [ -x "$CONTENTS/MacOS/python3.12" ]; then
    PYTHON="$CONTENTS/MacOS/python3.12"
    PYTHONPATH="$CONTENTS/Resources/python3.12/lib-dynload:$CONTENTS/Resources/python3.12/site-packages:$CONTENTS/Resources/python3.12:$REPO"
    export DYLD_LIBRARY_PATH="$CONTENTS/Frameworks"
    export QT_QPA_PLATFORM_PLUGIN_PATH="$CONTENTS/PlugIns/platforms"
    export QT_PLUGIN_PATH="$CONTENTS/PlugIns"
# Official 3.x bundle: interpreter at MacOS/bin/python3.9, stdlib in MacOS.
elif [ -x "$CONTENTS/MacOS/bin/python3.9" ]; then
    PYTHON="$CONTENTS/MacOS/bin/python3.9"
    export PYTHONHOME="$CONTENTS/MacOS"
    PYTHONPATH="$CONTENTS/Resources/python:$CONTENTS/Resources/python/site-packages:$REPO"
    export DYLD_LIBRARY_PATH="$CONTENTS/Frameworks:$CONTENTS/MacOS/lib"
    export QT_QPA_PLATFORM_PLUGIN_PATH="$CONTENTS/PlugIns/platforms"
    export QT_PLUGIN_PATH="$CONTENTS/PlugIns"
# MacPorts bundle: MacPorts python + Resources/python modules. Note: the
# MacPorts Qt5 currently fails to load QtWebKit on macOS 26, which breaks
# the qgis bindings import at the OS level, not at the plugin level.
elif [ -d "$CONTENTS/Resources/python/qgis" ]; then
    PYVER="$(ls /opt/local/Library/Frameworks/Python.framework/Versions 2>/dev/null | grep -E '^[0-9.]+$' | sort -V | tail -1)"
    [ -n "$PYVER" ] || { echo "MacPorts python not found" >&2; exit 1; }
    PYTHON="/opt/local/Library/Frameworks/Python.framework/Versions/$PYVER/bin/python$PYVER"
    [ -x "$PYTHON" ] || { echo "MacPorts interpreter not found at $PYTHON" >&2; exit 1; }
    PYTHONPATH="$CONTENTS/Resources/python:/opt/local/Library/Frameworks/Python.framework/Versions/$PYVER/lib/python$PYVER/site-packages:$REPO"
    export DYLD_LIBRARY_PATH="$CONTENTS/MacOS/lib:/opt/local/lib"
    export QGIS_PREFIX_PATH="$CONTENTS/MacOS"
    export QT_QPA_PLATFORM_PLUGIN_PATH="/opt/local/libexec/qt5/plugins/platforms"
else
    echo "No supported QGIS layout found in $APP_DIR" >&2
    exit 1
fi

export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
export PYTHONPATH
exec "$PYTHON" "$REPO/tools/QgisSmokeTest.py"

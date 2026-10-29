#!/bin/sh
# Run the plugin inside real QGIS, headless (offscreen Qt platform).
# Usage: tools/RunQgisSmoke.sh            (QGIS_APP=/path/to/QGIS.app to override)
set -eu

APP_DIR="${QGIS_APP:-/Applications/QGIS-final-4_2_3.app}"
CONTENTS="$APP_DIR/Contents"
PYTHON="$CONTENTS/MacOS/python3.12"

if [ ! -x "$PYTHON" ]; then
    echo "QGIS bundled interpreter not found at $PYTHON" >&2
    echo "Set QGIS_APP=/path/to/QGIS.app" >&2
    exit 1
fi

REPO="$(cd "$(dirname "$0")/.." && pwd)"

PYTHONPATH="$CONTENTS/Resources/python3.12/lib-dynload:$CONTENTS/Resources/python3.12/site-packages:$CONTENTS/Resources/python3.12:$REPO" \
DYLD_LIBRARY_PATH="$CONTENTS/Frameworks" \
QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" \
QT_QPA_PLATFORM_PLUGIN_PATH="$CONTENTS/PlugIns/platforms" \
exec "$PYTHON" "$REPO/tools/QgisSmokeTest.py"

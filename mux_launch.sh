#!/bin/sh
# HELP: Comet Desk - lightweight QWASAR companion
# GRID: Comet Desk

# muOS Andromeda application lifecycle wrapper.
. /opt/muos/script/var/func.sh

APP_DIR="/run/muos/storage/application/CometDesk"
export PATH="$APP_DIR/lib:$PATH"
export LD_LIBRARY_PATH="$APP_DIR/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
APP_BIN="love"
SETUP_APP "$APP_BIN" ""
LOG_DIR="$APP_DIR/data"
LOG_FILE="$LOG_DIR/comet-desk.log"

mkdir -p "$LOG_DIR"
export COMET_DESK_APP_DIR="$APP_DIR"
export COMET_DESK_PLATFORM="muos"

echo "$(date) === Comet Desk launch ===" >> "$LOG_FILE"

if [ ! -x "$APP_DIR/lib/love" ]; then
    echo "$(date) ERROR: bundled LÖVE launcher is missing or not executable" >> "$LOG_FILE"
    exit 1
fi
if [ ! -f "$APP_DIR/lib/liblove-11.5.so" ] || [ ! -f "$APP_DIR/lib/libluajit-5.1.so.2" ]; then
    echo "$(date) ERROR: bundled LÖVE runtime is incomplete" >> "$LOG_FILE"
    exit 1
fi
if [ ! -f "$APP_DIR/love/main.lua" ]; then
    echo "$(date) ERROR: application entry point is missing" >> "$LOG_FILE"
    exit 1
fi

cd "$APP_DIR" || exit 1
"$APP_DIR/lib/love" "$APP_DIR/love" >> "$LOG_FILE" 2>&1
RC=$?
echo "$(date) Comet Desk exit rc=$RC" >> "$LOG_FILE"
exit "$RC"

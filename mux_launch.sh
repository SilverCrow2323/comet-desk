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

# Comet Desk owns the desktop session lifecycle. The LÖVE control surface
# requests a session through one private file; this same launcher runs the
# integrated XFCE manager and re-opens Comet Desk when XFCE returns.
while :; do
    "$APP_DIR/lib/love" "$APP_DIR/love" >> "$LOG_FILE" 2>&1
    RC=$?
    REQUEST="$LOG_DIR/desktop-session.request"

    if [ -L "$REQUEST" ]; then
        echo "$(date) ERROR: refusing symbolic-link desktop session request" >> "$LOG_FILE"
        break
    fi
    if [ -f "$REQUEST" ]; then
        SLOT=""
        PROFILE="labwc"
        APP_ID=""
        {
            IFS= read -r SLOT || true
            IFS= read -r PROFILE || true
            IFS= read -r APP_ID || true
        } < "$REQUEST"
        rm -f "$REQUEST"
        case "$SLOT" in
            tf1|tf2)
                if [ ! -f "$APP_DIR/service/desktop_environment.py" ]; then
                    echo "$(date) ERROR: integrated desktop manager is missing" >> "$LOG_FILE"
                    break
                fi
                case "$PROFILE" in
                    labwc|xfce|lxde|lxqt|icewm|fluxbox|openbox) ;;
                    *) echo "$(date) ERROR: invalid desktop profile request" >> "$LOG_FILE"; break ;;
                esac
                case "$APP_ID" in
                    *[!a-zA-Z0-9._+-]*)
                        echo "$(date) ERROR: invalid Comet application id" >> "$LOG_FILE"
                        break
                        ;;
                esac
                echo "$(date) Comet Desk starting Debian profile $PROFILE from $SLOT (app=$APP_ID)" >> "$LOG_FILE"
                if [ -n "$APP_ID" ]; then
                    python3 "$APP_DIR/service/desktop_environment.py" session --slot "$SLOT" --profile "$PROFILE" --app-id "$APP_ID" --app-dir "$APP_DIR" >> "$LOG_FILE" 2>&1
                else
                    python3 "$APP_DIR/service/desktop_environment.py" session --slot "$SLOT" --profile "$PROFILE" --app-dir "$APP_DIR" >> "$LOG_FILE" 2>&1
                fi
                SESSION_RC=$?
                echo "$(date) XFCE session returned rc=$SESSION_RC; resuming Comet Desk" >> "$LOG_FILE"
                continue
                ;;
            *)
                echo "$(date) ERROR: invalid desktop session request" >> "$LOG_FILE"
                break
                ;;
        esac
    fi

    MEDIA_REQUEST="$LOG_DIR/media-session.request"
    if [ -L "$MEDIA_REQUEST" ]; then
        echo "$(date) ERROR: refusing symbolic-link media session request" >> "$LOG_FILE"
        rm -f "$MEDIA_REQUEST"
    elif [ -f "$MEDIA_REQUEST" ]; then
        echo "$(date) Comet Desk handing display to Media Vault" >> "$LOG_FILE"
        python3 "$APP_DIR/service/media_vault.py" playback --app-dir "$APP_DIR" >> "$LOG_FILE" 2>&1
        MEDIA_RC=$?
        echo "$(date) Media Vault playback returned rc=$MEDIA_RC; resuming Comet Desk" >> "$LOG_FILE"
        continue
    fi

    # A radio stream may have been playing in the background while the
    # frontend was visible. Leaving Comet always releases the media owner.
    if [ -f "$APP_DIR/service/media_vault.py" ]; then
        python3 "$APP_DIR/service/media_vault.py" stop --app-dir "$APP_DIR" >> "$LOG_FILE" 2>&1
    fi
    echo "$(date) Comet Desk exit rc=$RC" >> "$LOG_FILE"
    break
done
exit "$RC"

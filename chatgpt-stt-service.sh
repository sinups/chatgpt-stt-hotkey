#!/bin/bash
# ChatGPT STT Service — ждёт ChatGPT, запускает STT, перезапускает при падении.

export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$DIR/chatgpt_stt.py"
UPDATE_CHECK_FILE="/tmp/chatgpt-stt-last-update-check"

check_for_updates() {
    # Проверяем не чаще раза в 6 часов
    if [[ -f "$UPDATE_CHECK_FILE" ]]; then
        last=$(cat "$UPDATE_CHECK_FILE" 2>/dev/null)
        now=$(date +%s)
        diff=$(( now - last ))
        if (( diff < 21600 )); then
            return
        fi
    fi

    date +%s > "$UPDATE_CHECK_FILE"

    # Нет .git — нечего обновлять
    [[ ! -d "$DIR/.git" ]] && return

    # Проверяем remote (тихо, с таймаутом)
    cd "$DIR"
    git fetch origin main --quiet 2>/dev/null || return

    LOCAL=$(git rev-parse HEAD 2>/dev/null)
    REMOTE=$(git rev-parse origin/main 2>/dev/null)

    if [[ -n "$LOCAL" && -n "$REMOTE" && "$LOCAL" != "$REMOTE" ]]; then
        osascript -e 'display notification "Run: stt-update" with title "🎙️ ChatGPT STT" subtitle "Update available"' 2>/dev/null
    fi
}

while true; do
    # Ждём пока ChatGPT запустится
    while ! pgrep -xq "ChatGPT"; do
        sleep 3
    done

    # Проверяем обновления при запуске
    check_for_updates &

    # Запускаем STT
    "$PYTHON" "$SCRIPT" &
    PID=$!

    # Следим: если ChatGPT закрылся или скрипт упал — останавливаем
    while kill -0 "$PID" 2>/dev/null; do
        if ! pgrep -xq "ChatGPT"; then
            kill "$PID" 2>/dev/null
            wait "$PID" 2>/dev/null
            break
        fi
        sleep 2
    done

    wait "$PID" 2>/dev/null
    sleep 2
done

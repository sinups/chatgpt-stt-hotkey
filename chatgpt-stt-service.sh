#!/bin/bash
# ChatGPT STT Service — ждёт ChatGPT, запускает STT, перезапускает при падении.

export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
SCRIPT="/Users/sinups/Projects/chatgpt-stt-hotkey/chatgpt_stt.py"

while true; do
    # Ждём пока ChatGPT запустится
    while ! pgrep -xq "ChatGPT"; do
        sleep 3
    done

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

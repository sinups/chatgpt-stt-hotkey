#!/bin/bash
set -e

# ChatGPT STT Hotkey — установка
# Использование: curl -fsSL https://raw.githubusercontent.com/sinups/chatgpt-stt-hotkey/main/install.sh | bash

DIR="$HOME/Projects/chatgpt-stt-hotkey"
PLIST="$HOME/Library/LaunchAgents/com.sinups.chatgpt-stt.plist"
PYTHON=""

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  ChatGPT STT — Push-to-talk на Fn   ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# ─── Проверки ───

if [[ "$(uname)" != "Darwin" ]]; then
    echo "❌ Только macOS"; exit 1
fi

if ! ls /Applications/ChatGPT.app &>/dev/null; then
    echo "❌ ChatGPT не установлен"
    echo "   Скачайте: https://openai.com/chatgpt/mac/"
    exit 1
fi

# Python
for p in \
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3 \
    /usr/bin/python3; do
    if [[ -x "$p" ]]; then
        # Проверяем pyobjc
        if "$p" -c "import Quartz, AppKit" 2>/dev/null; then
            PYTHON="$p"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "❌ Python 3 с pyobjc не найден"
    echo "   Установите:"
    echo "   brew install python@3.12"
    echo "   pip3 install pyobjc-framework-Quartz pyobjc-framework-Cocoa"
    exit 1
fi

echo "✓ macOS $(sw_vers -productVersion)"
echo "✓ ChatGPT.app"
echo "✓ Python: $PYTHON"

# Homebrew
if ! command -v brew &>/dev/null; then
    echo "❌ Homebrew не найден"
    echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi
echo "✓ Homebrew"

# cliclick
if ! command -v cliclick &>/dev/null; then
    echo "→ Устанавливаю cliclick..."
    brew install cliclick
fi
echo "✓ cliclick"

# ─── Скачиваем / обновляем ───

if [[ -d "$DIR/.git" ]]; then
    echo "→ Обновляю..."
    cd "$DIR"
    git pull --ff-only 2>/dev/null || true
else
    echo "→ Скачиваю..."
    mkdir -p "$DIR"
    cd "$DIR"
    if command -v git &>/dev/null; then
        git clone https://github.com/sinups/chatgpt-stt-hotkey.git "$DIR" 2>/dev/null || {
            # Fallback: скачиваем файлы напрямую
            curl -fsSL "https://raw.githubusercontent.com/sinups/chatgpt-stt-hotkey/main/chatgpt_stt.py" -o chatgpt_stt.py
            curl -fsSL "https://raw.githubusercontent.com/sinups/chatgpt-stt-hotkey/main/chatgpt-stt-service.sh" -o chatgpt-stt-service.sh
        }
    fi
fi

chmod +x "$DIR/chatgpt_stt.py" "$DIR/chatgpt-stt-service.sh" 2>/dev/null

# Прописываем правильный Python в service.sh
sed -i '' "s|^PYTHON=.*|PYTHON=\"$PYTHON\"|" "$DIR/chatgpt-stt-service.sh"

# ─── Служба ───

echo "→ Настраиваю службу..."

# Останавливаем старую если есть
launchctl unload "$PLIST" 2>/dev/null || true

cat > "$PLIST" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sinups.chatgpt-stt</string>
    <key>ProgramArguments</key>
    <array>
        <string>$DIR/chatgpt-stt-service.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/chatgpt-stt.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/chatgpt-stt.log</string>
    <key>ProcessType</key>
    <string>Interactive</string>
</dict>
</plist>
PLISTEOF

# ─── Accessibility ───

# Определяем Python.app
PYTHON_APP=$(dirname "$(dirname "$(dirname "$PYTHON")")")/Resources/Python.app
if [[ ! -d "$PYTHON_APP" ]]; then
    PYTHON_APP="$PYTHON"
fi

echo ""
echo "┌─────────────────────────────────────────────┐"
echo "│  ⚠️  Нужно разрешить Accessibility           │"
echo "├─────────────────────────────────────────────┤"
echo "│  1. Откроется System Settings               │"
echo "│  2. Нажми + внизу списка                    │"
echo "│  3. Cmd+Shift+G → вставь путь:             │"
echo "│     $PYTHON_APP"
echo "│  4. Нажми Open, убедись что ✓ стоит         │"
echo "└─────────────────────────────────────────────┘"
echo ""
read -p "Нажми Enter чтобы открыть настройки..."

open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"

echo ""
read -p "Добавил Python.app в Accessibility? (y/n) " answer
if [[ "$answer" != "y" && "$answer" != "Y" ]]; then
    echo "⚠️  Без Accessibility скрипт не сможет управлять виджетом."
    echo "   Добавь позже и перезапусти: stt-restart"
fi

# ─── Запуск ───

echo "→ Запускаю..."
launchctl load "$PLIST"
sleep 2

if launchctl list | grep -q "com.sinups.chatgpt-stt"; then
    echo "✓ Служба запущена"
else
    echo "⚠️  Служба не запустилась. Проверь: stt-log"
fi

# ─── Алиасы ───

SHELL_RC="$HOME/.zshrc"
[[ -f "$HOME/.bashrc" ]] && [[ ! -f "$HOME/.zshrc" ]] && SHELL_RC="$HOME/.bashrc"

if ! grep -q "stt-status" "$SHELL_RC" 2>/dev/null; then
    cat >> "$SHELL_RC" << 'ALIASEOF'

# ChatGPT STT service
alias stt-status='launchctl list com.sinups.chatgpt-stt 2>/dev/null && echo "Log:" && tail -3 /tmp/chatgpt-stt.log'
alias stt-restart='launchctl unload ~/Library/LaunchAgents/com.sinups.chatgpt-stt.plist 2>/dev/null; launchctl load ~/Library/LaunchAgents/com.sinups.chatgpt-stt.plist && echo "STT restarted"'
alias stt-stop='launchctl unload ~/Library/LaunchAgents/com.sinups.chatgpt-stt.plist 2>/dev/null && echo "STT stopped"'
alias stt-log='tail -20 /tmp/chatgpt-stt.log'
ALIASEOF
    echo "✓ Алиасы добавлены в $SHELL_RC"
fi

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  ✅ Установка завершена!             ║"
echo "  ║                                      ║"
echo "  ║  Fn (зажать) → говори → отпусти     ║"
echo "  ║  Cmd+V для вставки                   ║"
echo "  ║                                      ║"
echo "  ║  stt-status  — статус                ║"
echo "  ║  stt-restart — перезапуск            ║"
echo "  ║  stt-stop    — остановка             ║"
echo "  ║  stt-log     — логи                  ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

#!/bin/bash
set -e

# ChatGPT STT Hotkey — установка
# curl -fsSL https://raw.githubusercontent.com/sinups/chatgpt-stt-hotkey/main/install.sh | bash

REPO="https://github.com/sinups/chatgpt-stt-hotkey.git"
RAW="https://raw.githubusercontent.com/sinups/chatgpt-stt-hotkey/main"
DIR="$HOME/Projects/chatgpt-stt-hotkey"
LABEL="com.chatgpt-stt"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  ChatGPT STT — Push-to-talk на Fn   ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# ─── macOS ───
if [[ "$(uname)" != "Darwin" ]]; then
    echo "❌ Только macOS"; exit 1
fi
echo "✓ macOS $(sw_vers -productVersion)"

# ─── ChatGPT ───
if [[ ! -d "/Applications/ChatGPT.app" ]]; then
    echo "❌ ChatGPT не установлен → https://openai.com/chatgpt/mac/"
    exit 1
fi
echo "✓ ChatGPT.app"

# ─── Python с pyobjc ───
PYTHON=""
for p in \
    /Library/Frameworks/Python.framework/Versions/3.*/bin/python3 \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3; do
    if [[ -x "$p" ]] && "$p" -c "import Quartz, AppKit" 2>/dev/null; then
        PYTHON="$p"
        break
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "❌ Python 3 с pyobjc не найден"
    echo ""
    echo "   brew install python@3.12"
    echo "   pip3 install pyobjc-framework-Quartz pyobjc-framework-Cocoa"
    exit 1
fi
echo "✓ Python: $PYTHON"

# ─── Homebrew + cliclick ───
if ! command -v brew &>/dev/null; then
    echo "❌ Homebrew → https://brew.sh"
    exit 1
fi

if ! command -v cliclick &>/dev/null; then
    echo "→ Устанавливаю cliclick..."
    brew install cliclick
fi
echo "✓ cliclick"

# ─── Скачиваем ───
echo "→ Скачиваю..."

if [[ -d "$DIR/.git" ]]; then
    cd "$DIR"
    git pull --ff-only 2>/dev/null || true
elif command -v git &>/dev/null; then
    rm -rf "$DIR"
    git clone "$REPO" "$DIR" 2>/dev/null || {
        mkdir -p "$DIR"
        curl -fsSL "$RAW/chatgpt_stt.py" -o "$DIR/chatgpt_stt.py"
        curl -fsSL "$RAW/chatgpt-stt-service.sh" -o "$DIR/chatgpt-stt-service.sh"
    }
else
    mkdir -p "$DIR"
    curl -fsSL "$RAW/chatgpt_stt.py" -o "$DIR/chatgpt_stt.py"
    curl -fsSL "$RAW/chatgpt-stt-service.sh" -o "$DIR/chatgpt-stt-service.sh"
fi

cd "$DIR"
chmod +x chatgpt_stt.py chatgpt-stt-service.sh 2>/dev/null || true
sed -i '' "s|^PYTHON=.*|PYTHON=\"$PYTHON\"|" chatgpt-stt-service.sh

echo "✓ Файлы в $DIR"

# ─── Служба launchd ───
echo "→ Настраиваю службу..."
launchctl unload "$PLIST" 2>/dev/null || true

cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
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
EOF

echo "✓ Служба настроена"

# ─── Accessibility ───
PYTHON_APP=""
PYDIR="$(dirname "$(dirname "$PYTHON")")"
if [[ -d "$PYDIR/Resources/Python.app" ]]; then
    PYTHON_APP="$PYDIR/Resources/Python.app"
fi

echo ""
echo "┌───────────────────────────────────────────────┐"
echo "│  ⚠️  Нужно добавить Python в Accessibility     │"
echo "├───────────────────────────────────────────────┤"
echo "│  1. Откроется System Settings                 │"
echo "│  2. Нажми + внизу                             │"
echo "│  3. Cmd+Shift+G, вставь:                     │"
if [[ -n "$PYTHON_APP" ]]; then
echo "│     $PYTHON_APP"
else
echo "│     $PYTHON"
fi
echo "│  4. Open → галочка ✓                         │"
echo "└───────────────────────────────────────────────┘"
echo ""

open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"

# read из /dev/tty для совместимости с curl | bash
if [[ -t 0 ]]; then
    read -p "Добавил? (Enter) "
else
    read -p "Добавил? (Enter) " < /dev/tty 2>/dev/null || sleep 5
fi

# ─── Запуск ───
echo "→ Запускаю службу..."
launchctl load "$PLIST" 2>/dev/null || true
sleep 2

if launchctl list 2>/dev/null | grep -q "$LABEL"; then
    echo "✓ Служба запущена"
else
    echo "⚠️  Проверь: tail -10 /tmp/chatgpt-stt.log"
fi

# ─── Алиасы ───
RC="$HOME/.zshrc"
[[ ! -f "$RC" ]] && RC="$HOME/.bashrc"

if [[ -f "$RC" ]] && ! grep -q "chatgpt-stt" "$RC" 2>/dev/null; then
    {
        echo ""
        echo "# ChatGPT STT"
        echo "alias stt-status='launchctl list $LABEL 2>/dev/null && tail -3 /tmp/chatgpt-stt.log'"
        echo "alias stt-restart='launchctl unload $PLIST 2>/dev/null; launchctl load $PLIST && echo \"STT restarted\"'"
        echo "alias stt-stop='launchctl unload $PLIST 2>/dev/null && echo \"STT stopped\"'"
        echo "alias stt-log='tail -20 /tmp/chatgpt-stt.log'"
    } >> "$RC"
    echo "✓ Алиасы (source $RC)"
fi

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  ✅ Готово!                          ║"
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

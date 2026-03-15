# ChatGPT STT Hotkey

Push-to-talk на клавише **Fn** для macOS через виджет ChatGPT.

Зажми Fn → говори → отпусти → текст в буфере обмена → Cmd+V.

## Установка

```bash
curl -fsSL https://raw.githubusercontent.com/sinups/chatgpt-stt-hotkey/main/install.sh | bash
```

## Требования

- macOS 13+
- [ChatGPT desktop app](https://openai.com/chatgpt/mac/) с подпиской Plus
- Homebrew

## Как работает

1. **Fn зажат** — открывается виджет ChatGPT, нажимается "Расшифровать голос"
2. **Говоришь** — ChatGPT записывает и транскрибирует
3. **Fn отпущен** — запись останавливается, текст копируется в буфер обмена
4. **Cmd+V** — вставляешь куда угодно

Виджет ChatGPT виден во время записи как индикатор. После транскрипции автоматически закрывается.

## Управление

```bash
stt-status    # статус службы
stt-restart   # перезапуск
stt-stop      # остановка
stt-log       # логи
```

## Удаление

```bash
launchctl unload ~/Library/LaunchAgents/com.sinups.chatgpt-stt.plist
rm ~/Library/LaunchAgents/com.sinups.chatgpt-stt.plist
rm -rf ~/Projects/chatgpt-stt-hotkey
```

## Технические детали

- **CGEventTap** для захвата Fn (обходит ограничения macOS на Fn)
- **CGEvent** для отправки Option+Space (обходит зажатый Fn)
- **cliclick** для кликов по UI элементам виджета
- **SkyLight framework** (опционально) для управления прозрачностью окон
- **launchd** служба с автозапуском и мониторингом ChatGPT процесса

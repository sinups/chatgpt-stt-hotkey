#!/usr/bin/env python3
"""
Тесты стабильности ChatGPT STT Hotkey.

python3 test_stt.py
"""

import subprocess
import time
import sys
import json

PASS = 0
FAIL = 0


def log(msg):
    print(msg)
    sys.stdout.flush()


def ok(name):
    global PASS
    PASS += 1
    log(f"  PASS  {name}")


def fail(name, reason=""):
    global FAIL
    FAIL += 1
    log(f"  FAIL  {name} — {reason}")


def jxa(s, t=5):
    try:
        r = subprocess.run(['osascript', '-l', 'JavaScript', '-e', s],
                           capture_output=True, text=True, timeout=t)
        return r.stdout.strip()
    except:
        return ""


def click(x, y):
    subprocess.run(['cliclick', f'c:{x},{y}'], capture_output=True, timeout=3)


def open_widget():
    import Quartz
    evt = Quartz.CGEventCreateKeyboardEvent(None, 49, True)
    Quartz.CGEventSetFlags(evt, Quartz.kCGEventFlagMaskAlternate)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)
    evt2 = Quartz.CGEventCreateKeyboardEvent(None, 49, False)
    Quartz.CGEventSetFlags(evt2, Quartz.kCGEventFlagMaskAlternate)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt2)


def close_widget():
    import Quartz
    evt = Quartz.CGEventCreateKeyboardEvent(None, 53, True)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)
    evt2 = Quartz.CGEventCreateKeyboardEvent(None, 53, False)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt2)


def widget_count():
    r = jxa('''
    function run() {
        const p = Application("System Events").processes["ChatGPT"];
        let c = 0;
        for (let w = 0; w < p.windows.length; w++) {
            if (p.windows[w].size()[0] < 500) c++;
        }
        return "" + c;
    }
    run();
    ''')
    try:
        return int(r)
    except:
        return -1


def find_mic():
    r = jxa('''
    function run() {
        const p = Application("System Events").processes["ChatGPT"];
        for (let w = 0; w < p.windows.length; w++) {
            let sz = p.windows[w].size();
            if (sz[0] < 500) {
                let elems = p.windows[w].entireContents();
                for (let i = 0; i < elems.length; i++) {
                    try {
                        let h = elems[i].help();
                        if (h && h.includes("Расшифровать голос")) {
                            let pos = elems[i].position();
                            let s = elems[i].size();
                            return JSON.stringify({x:pos[0]+s[0]/2, y:pos[1]+s[1]/2});
                        }
                    } catch(e) {}
                }
            }
        }
        return "";
    }
    run();
    ''')
    if r:
        try:
            d = json.loads(r)
            return int(d['x']), int(d['y'])
        except:
            pass
    return None


def btn_count():
    r = jxa('''
    function run() {
        const p = Application("System Events").processes["ChatGPT"];
        for (let w = 0; w < p.windows.length; w++) {
            let sz = p.windows[w].size();
            if (sz[0] < 500) return "" + p.windows[w].groups[0].buttons.length;
        }
        return "0";
    }
    run();
    ''')
    try:
        return int(r)
    except:
        return 0


def find_stop():
    r = jxa('''
    function run() {
        const p = Application("System Events").processes["ChatGPT"];
        for (let w = 0; w < p.windows.length; w++) {
            let sz = p.windows[w].size();
            if (sz[0] < 500) {
                let btns = p.windows[w].groups[0].buttons;
                if (btns.length <= 4) {
                    for (let i = 0; i < btns.length; i++) {
                        let h = ""; try { h = btns[i].help(); } catch(e) {}
                        let pos = btns[i].position();
                        let s = btns[i].size();
                        if (!h && s[0] >= 28 && s[0] <= 40 && pos[0] > 800) {
                            return JSON.stringify({x:pos[0]+s[0]/2, y:pos[1]+s[1]/2});
                        }
                    }
                }
            }
        }
        return "";
    }
    run();
    ''')
    if r:
        try:
            d = json.loads(r)
            return int(d['x']), int(d['y'])
        except:
            pass
    return None


def read_text():
    return jxa('''
    function run() {
        const p = Application("System Events").processes["ChatGPT"];
        for (let w = 0; w < p.windows.length; w++) {
            let sz = p.windows[w].size();
            if (sz[0] < 500) {
                let sas = p.windows[w].groups[0].scrollAreas;
                for (let i = 0; i < sas.length; i++) {
                    let tas = sas[i].textAreas;
                    if (tas.length > 0) return tas[0].value() || "";
                }
            }
        }
        return "";
    }
    run();
    ''')


def clear_text():
    subprocess.run(['osascript', '-e', '''
        tell application "System Events"
            tell process "ChatGPT"
                keystroke "a" using command down
                delay 0.05
                key code 51
            end tell
        end tell
    '''], capture_output=True, timeout=3)


# ═══════════════════════════════════════════
#  Тесты
# ═══════════════════════════════════════════

def test_prerequisites():
    log("\n--- Зависимости ---")

    r = subprocess.run(['which', 'cliclick'], capture_output=True)
    if r.returncode == 0:
        ok("cliclick установлен")
    else:
        fail("cliclick", "не найден")

    r = subprocess.run(
        ['osascript', '-e', 'tell application "System Events" to get name of every process whose name is "ChatGPT"'],
        capture_output=True, text=True)
    if 'ChatGPT' in r.stdout:
        ok("ChatGPT запущен")
    else:
        fail("ChatGPT", "не запущен")


def test_widget_open_close():
    log("\n--- Виджет: открытие/закрытие ---")

    # Убедимся что виджет закрыт
    close_widget()
    time.sleep(0.5)

    c = widget_count()
    if c == 0:
        ok("Виджет закрыт изначально")
    else:
        fail("Исходное состояние", f"виджетов: {c}")

    open_widget()
    time.sleep(0.8)
    c = widget_count()
    if c == 1:
        ok("Виджет открылся")
    else:
        fail("Открытие виджета", f"виджетов: {c}")

    close_widget()
    time.sleep(0.5)
    c = widget_count()
    if c == 0:
        ok("Виджет закрылся")
    else:
        fail("Закрытие виджета", f"виджетов: {c}")


def test_mic_button():
    log("\n--- Кнопка микрофона ---")

    open_widget()
    time.sleep(0.8)

    mic = find_mic()
    if mic:
        ok(f"Микрофон найден: {mic}")
    else:
        fail("Поиск микрофона")
        close_widget()
        return

    # Клик → запись
    click(mic[0], mic[1])
    time.sleep(1)

    bc = btn_count()
    if bc <= 4:
        ok(f"Запись началась (кнопок: {bc})")
    else:
        fail("Старт записи", f"кнопок: {bc}")
        close_widget()
        return

    # Стоп
    stop = find_stop()
    if stop:
        ok(f"Кнопка стоп: {stop}")
        click(stop[0], stop[1])
        time.sleep(1)
        bc2 = btn_count()
        if bc2 > 4:
            ok(f"Запись остановлена (кнопок: {bc2})")
        else:
            fail("Остановка записи", f"кнопок: {bc2}")
    else:
        fail("Кнопка стоп не найдена")

    close_widget()
    time.sleep(0.5)


def test_multiple_cycles():
    log("\n--- 3 цикла подряд ---")

    for i in range(3):
        open_widget()
        time.sleep(0.7)
        clear_text()
        time.sleep(0.1)

        mic = find_mic()
        if not mic:
            fail(f"Цикл {i+1}: микрофон")
            close_widget()
            time.sleep(0.5)
            continue

        click(mic[0], mic[1])
        time.sleep(0.5)

        bc = btn_count()
        if bc > 4:
            # Retry
            click(mic[0], mic[1])
            time.sleep(0.5)
            bc = btn_count()

        if bc > 4:
            fail(f"Цикл {i+1}: запись не началась")
            close_widget()
            time.sleep(0.5)
            continue

        # Записываем 2 секунды
        time.sleep(2)

        stop = find_stop()
        if not stop:
            fail(f"Цикл {i+1}: стоп не найден")
            close_widget()
            time.sleep(0.5)
            continue

        click(stop[0], stop[1])
        time.sleep(3)

        text = read_text()
        if text and text.strip():
            ok(f"Цикл {i+1}: '{text.strip()[:60]}'")
        else:
            ok(f"Цикл {i+1}: запись/стоп ОК (тишина)")

        close_widget()
        time.sleep(0.5)


def test_rapid_open_close():
    log("\n--- Быстрое открытие/закрытие (5 раз) ---")

    success = 0
    for i in range(5):
        open_widget()
        time.sleep(0.5)
        c = widget_count()
        if c >= 1:
            success += 1
        close_widget()
        time.sleep(0.3)

    if success == 5:
        ok(f"Все 5 циклов open/close")
    else:
        fail(f"Быстрый open/close", f"успешно {success}/5")

    # Убедимся что виджет закрыт
    time.sleep(0.5)
    c = widget_count()
    if c == 0:
        ok("Виджет закрыт после серии")
    else:
        fail("Утечка виджетов", f"осталось: {c}")
        close_widget()


def test_state_after_error():
    log("\n--- Восстановление после ошибки ---")

    # Открываем виджет, начинаем запись, закрываем виджет БЕЗ стопа
    open_widget()
    time.sleep(0.7)

    mic = find_mic()
    if not mic:
        fail("Подготовка: микрофон")
        close_widget()
        return

    click(mic[0], mic[1])
    time.sleep(0.5)

    bc = btn_count()
    if bc <= 4:
        ok("Запись начата для теста ошибки")
    else:
        fail("Запись не началась для теста")
        close_widget()
        return

    # Закрываем виджет прямо во время записи
    close_widget()
    time.sleep(0.5)

    # Проверяем: можем ли открыть заново и начать нормально?
    open_widget()
    time.sleep(0.7)

    mic2 = find_mic()
    if mic2:
        ok("Восстановление: микрофон найден после аварийного закрытия")
    else:
        fail("Восстановление: микрофон не найден")

    close_widget()
    time.sleep(0.3)


# ═══════════════════════════════════════════

def main():
    log("=" * 50)
    log("  ChatGPT STT — Тесты стабильности")
    log("=" * 50)

    test_prerequisites()
    test_widget_open_close()
    test_mic_button()
    test_multiple_cycles()
    test_rapid_open_close()
    test_state_after_error()

    log("\n" + "=" * 50)
    log(f"  Результат: {PASS} PASS, {FAIL} FAIL")
    log("=" * 50)

    sys.exit(1 if FAIL > 0 else 0)


if __name__ == '__main__':
    main()

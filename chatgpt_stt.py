#!/usr/bin/env python3
"""
ChatGPT STT — Push-to-talk на Fn через виджет.

Зажми Fn → виджет + запись.
Отпусти Fn → текст в буфер → Cmd+V.
"""

import subprocess
import time
import threading
import signal
import sys
import json
import Quartz
from AppKit import NSWorkspace, NSPasteboard, NSStringPboardType


def log(msg):
    print(msg)
    sys.stdout.flush()


# ─── Состояние ───
state = "idle"
state_lock = threading.Lock()
fn_pressed = False
last_fn_time = 0
FN_FLAG = 0x800000
DEBOUNCE = 0.4

# Кэш: смещение кнопки микрофона от левого верхнего угла виджета
_cached_mic_dx = None
_cached_mic_dy = None


def _jxa(s, t=5):
    try:
        r = subprocess.run(['osascript', '-l', 'JavaScript', '-e', s],
                           capture_output=True, text=True, timeout=t)
        return r.stdout.strip()
    except:
        return ""


def _click(x, y):
    subprocess.run(['cliclick', f'c:{x},{y}'], capture_output=True, timeout=3)


def _clipboard(text):
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSStringPboardType)


def _active_app():
    ws = NSWorkspace.sharedWorkspace()
    a = ws.frontmostApplication()
    return a.bundleIdentifier() if a else None


def _open_widget():
    """Открыть виджет через CGEvent Option+Space (обходит зажатый Fn)."""
    evt = Quartz.CGEventCreateKeyboardEvent(None, 49, True)
    Quartz.CGEventSetFlags(evt, Quartz.kCGEventFlagMaskAlternate)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)
    evt2 = Quartz.CGEventCreateKeyboardEvent(None, 49, False)
    Quartz.CGEventSetFlags(evt2, Quartz.kCGEventFlagMaskAlternate)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt2)


def _close_widget():
    """Закрыть виджет: фокус на ChatGPT → Escape."""
    # Сначала убеждаемся что ChatGPT в фокусе
    subprocess.run(['osascript', '-e', 'tell application "ChatGPT" to activate'],
                   capture_output=True, timeout=3)
    time.sleep(0.15)
    # Escape
    evt = Quartz.CGEventCreateKeyboardEvent(None, 53, True)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)
    evt2 = Quartz.CGEventCreateKeyboardEvent(None, 53, False)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt2)


def _has_widget():
    """Проверить, открыт ли виджет."""
    r = _jxa('''
    function run() {
        const p = Application("System Events").processes["ChatGPT"];
        for (let w = 0; w < p.windows.length; w++) {
            if (p.windows[w].size()[0] < 500) return "yes";
        }
        return "no";
    }
    run();
    ''')
    return r == "yes"


def _get_widget_pos():
    """Получить позицию виджета: {wx, wy}."""
    r = _jxa('''
    function run() {
        const p = Application("System Events").processes["ChatGPT"];
        for (let w = 0; w < p.windows.length; w++) {
            let sz = p.windows[w].size();
            if (sz[0] < 500) {
                let pos = p.windows[w].position();
                return JSON.stringify({wx: pos[0], wy: pos[1]});
            }
        }
        return "";
    }
    run();
    ''')
    if r:
        try:
            return json.loads(r)
        except:
            pass
    return None


def _find_mic_in_widget():
    """Найти микрофон и вернуть (абс_x, абс_y, offset_dx, offset_dy)."""
    r = _jxa('''
    function run() {
        const p = Application("System Events").processes["ChatGPT"];
        for (let w = 0; w < p.windows.length; w++) {
            let sz = p.windows[w].size();
            if (sz[0] < 500) {
                let wpos = p.windows[w].position();
                let elems = p.windows[w].entireContents();
                for (let i = 0; i < elems.length; i++) {
                    try {
                        let h = elems[i].help();
                        if (h && h.includes("Расшифровать голос")) {
                            let pos = elems[i].position();
                            let s = elems[i].size();
                            let cx = pos[0]+s[0]/2, cy = pos[1]+s[1]/2;
                            return JSON.stringify({
                                x: cx, y: cy,
                                dx: cx - wpos[0], dy: cy - wpos[1]
                            });
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
            return json.loads(r)
        except:
            pass
    return None


def _find_stop_in_widget():
    """Найти стоп-кнопку (галочку) в виджете."""
    r = _jxa('''
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


def _btn_count():
    """Количество кнопок в виджете (3 = запись, 9+ = обычный)."""
    r = _jxa('''
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


def _read_widget_text():
    return _jxa('''
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


def _clear_widget():
    subprocess.run(['osascript', '-e', '''
        tell application "System Events"
            tell process "ChatGPT"
                keystroke "a" using command down
                delay 0.05
                key code 51
            end tell
        end tell
    '''], capture_output=True, timeout=3)


def _restore_app(bundle_id):
    if bundle_id:
        subprocess.run(['osascript', '-e', f'''
            tell application "System Events"
                try
                    set t to first process whose bundle identifier is "{bundle_id}"
                    set frontmost of t to true
                end try
            end tell
        '''], capture_output=True, timeout=3)


# ─── Цикл записи ───

def _find_cancel_in_widget():
    """Найти кнопку X (отмена) в режиме записи — слева."""
    r = _jxa('''
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
                        if (!h && s[0] >= 30 && s[0] <= 45 && pos[0] < 800) {
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


def _force_close():
    """Принудительно закрыть виджет: отменить запись если идёт, потом Escape."""
    for _ in range(3):
        if not _has_widget():
            return
        bc = _btn_count()
        if 0 < bc <= 4:
            cancel = _find_cancel_in_widget()
            if cancel:
                _click(cancel[0], cancel[1])
                time.sleep(0.5)
        _close_widget()
        time.sleep(0.5)


def _wait_normal(timeout=5):
    """Ждём пока кнопки вернутся в нормальный режим (> 4) после стопа."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        bc = _btn_count()
        if bc > 4:
            return True
        time.sleep(0.3)
    return False


def do_recording():
    global state, _cached_mic_dx, _cached_mic_dy

    with state_lock:
        if state != "idle":
            return
        state = "recording"

    prev_app = _active_app()

    try:
        # 0. Закрываем зависший виджет если есть
        if _has_widget():
            _force_close()
            time.sleep(0.3)  # пауза после закрытия перед повторным открытием

        # 1. Открываем виджет (поллинг)
        _open_widget()
        widget_ready = False
        for _ in range(20):
            time.sleep(0.05)
            if _has_widget():
                widget_ready = True
                break

        if not widget_ready:
            time.sleep(0.3)
            _open_widget()
            for _ in range(20):
                time.sleep(0.05)
                if _has_widget():
                    widget_ready = True
                    break

        if not widget_ready:
            log("[!] Виджет не открылся")
            return

        # 2. Очищаем поле
        _clear_widget()
        time.sleep(0.1)

        # 3. Кликаем микрофон (кэш или поиск)
        mic_x, mic_y = None, None

        if _cached_mic_dx is not None:
            wpos = _get_widget_pos()
            if wpos:
                mic_x = int(wpos['wx'] + _cached_mic_dx)
                mic_y = int(wpos['wy'] + _cached_mic_dy)

        if mic_x is None:
            mic_info = _find_mic_in_widget()
            if mic_info:
                mic_x, mic_y = int(mic_info['x']), int(mic_info['y'])
                _cached_mic_dx = mic_info['dx']
                _cached_mic_dy = mic_info['dy']

        if mic_x is None:
            log("[!] Микрофон не найден")
            _force_close()
            return

        _click(mic_x, mic_y)

        # Поллим начало записи (вместо sleep 0.5)
        rec_started = False
        for _ in range(15):  # макс 0.75 сек
            time.sleep(0.05)
            bc = _btn_count()
            if 0 < bc <= 4:
                rec_started = True
                break

        if not rec_started:
            # Retry: сбрасываем кэш, ищем заново
            _cached_mic_dx = None
            _cached_mic_dy = None
            mic_info = _find_mic_in_widget()
            if mic_info:
                _click(int(mic_info['x']), int(mic_info['y']))
                for _ in range(15):
                    time.sleep(0.05)
                    bc = _btn_count()
                    if 0 < bc <= 4:
                        rec_started = True
                        break

        if not rec_started:
            log("[!] Запись не началась")
            _force_close()
            return

        log("[*] Запись...")

        # 5. Ждём отпускания Fn (таймаут 60 сек)
        deadline = time.time() + 60
        while fn_pressed and time.time() < deadline:
            time.sleep(0.05)

        # 6. Стоп — запись может уже остановиться сама (тишина)
        bc = _btn_count()
        if 0 < bc <= 4:
            # Ещё записывает — кликаем стоп
            stop = _find_stop_in_widget()
            if stop:
                _click(stop[0], stop[1])
            _wait_normal(5)

        # 7. Ждём транскрипцию
        text = ""
        for _ in range(20):
            time.sleep(0.5)
            t = _read_widget_text()
            if t and t.strip():
                text = t.strip()
                break

        # 9. Копируем и закрываем
        if text:
            _clipboard(text)
            log(f"[+] {text[:80]}{'...' if len(text) > 80 else ''}")
        else:
            log("[-] Пусто")

        _force_close()
        time.sleep(0.15)
        _restore_app(prev_app)

    except Exception as e:
        log(f"[!] Ошибка: {e}")
        _force_close()

    finally:
        with state_lock:
            state = "idle"


# ─── Event callback ───

def event_cb(proxy, etype, event, refcon):
    global fn_pressed, last_fn_time

    # Event tap может отключиться — проверяем
    if etype == Quartz.kCGEventTapDisabledByTimeout:
        Quartz.CGEventTapEnable(proxy, True)
        return event

    if etype == Quartz.kCGEventFlagsChanged:
        flags = Quartz.CGEventGetFlags(event)
        fn = bool(flags & FN_FLAG)
        now = time.time()
        mods = (Quartz.kCGEventFlagMaskCommand | Quartz.kCGEventFlagMaskAlternate |
                Quartz.kCGEventFlagMaskShift | Quartz.kCGEventFlagMaskControl)

        if fn and not fn_pressed and not (flags & mods):
            if now - last_fn_time < DEBOUNCE:
                return event
            last_fn_time = now
            fn_pressed = True
            threading.Thread(target=do_recording, daemon=True).start()
        elif not fn and fn_pressed:
            fn_pressed = False
            last_fn_time = now

    return event


# ─── Main ───

def main():
    log("=" * 40)
    log("  ChatGPT STT — Fn push-to-talk")
    log("=" * 40)

    if '--test' in sys.argv:
        log("\n[TEST] Открываю виджет...")
        _open_widget()
        time.sleep(0.8)
        _clear_widget()
        time.sleep(0.2)
        mic_info = _find_mic_in_widget()
        assert mic_info, "Микрофон не найден!"
        log(f"[TEST] Микрофон: ({int(mic_info['x'])}, {int(mic_info['y'])})")
        _click(int(mic_info['x']), int(mic_info['y']))
        time.sleep(1)
        stop = _find_stop_in_widget()
        if stop:
            log("[TEST] Запись! Говори 3 сек...")
            time.sleep(3)
            _click(stop[0], stop[1])
            time.sleep(3)
            text = _read_widget_text()
            if text and text.strip():
                _clipboard(text.strip())
                log(f"[TEST] '{text.strip()[:100]}'")
                log("[TEST] В буфере!")
            else:
                log("[TEST] Пусто")
        else:
            log("[TEST] Запись не началась")
        _close_widget()
        log("[TEST] Готово!\n")
        return

    if subprocess.run(['which', 'cliclick'], capture_output=True).returncode != 0:
        log("[!] brew install cliclick"); sys.exit(1)

    r = subprocess.run(
        ['osascript', '-e', 'tell application "System Events" to get name of every process whose name is "ChatGPT"'],
        capture_output=True, text=True)
    if 'ChatGPT' not in r.stdout:
        log("[!] Запустите ChatGPT"); sys.exit(1)

    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap, Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionListenOnly,
        Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged),
        event_cb, None)
    if not tap:
        log("[!] Accessibility!"); sys.exit(1)

    src = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
    Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetCurrent(), src, Quartz.kCFRunLoopDefaultMode)
    Quartz.CGEventTapEnable(tap, True)

    log("[*] Fn → говори → отпусти → Cmd+V")
    log("[*] Ctrl+C выход\n")

    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    try:
        Quartz.CFRunLoopRun()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()

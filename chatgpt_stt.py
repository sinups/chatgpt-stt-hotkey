#!/usr/bin/env python3
"""
ChatGPT STT — Push-to-talk on Fn via ChatGPT widget.

Hold Fn -> widget opens, recording starts.
Release Fn -> transcription copied to clipboard -> Cmd+V to paste.
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


state = "idle"
state_lock = threading.Lock()
fn_pressed = False
last_fn_time = 0
FN_FLAG = 0x800000
DEBOUNCE = 0.4

_cached_mic_dx = None
_cached_mic_dy = None


def _jxa(s, t=5):
    try:
        r = subprocess.run(['osascript', '-l', 'JavaScript', '-e', s],
                           capture_output=True, text=True, timeout=t)
        return r.stdout.strip()
    except Exception:
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
    evt = Quartz.CGEventCreateKeyboardEvent(None, 49, True)
    Quartz.CGEventSetFlags(evt, Quartz.kCGEventFlagMaskAlternate)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)
    evt2 = Quartz.CGEventCreateKeyboardEvent(None, 49, False)
    Quartz.CGEventSetFlags(evt2, Quartz.kCGEventFlagMaskAlternate)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt2)


def _close_widget():
    subprocess.run(['osascript', '-e', 'tell application "ChatGPT" to activate'],
                   capture_output=True, timeout=3)
    time.sleep(0.15)
    evt = Quartz.CGEventCreateKeyboardEvent(None, 53, True)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)
    evt2 = Quartz.CGEventCreateKeyboardEvent(None, 53, False)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt2)


def _has_widget():
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
        except Exception:
            pass
    return None


def _find_mic_in_widget():
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
        except Exception:
            pass
    return None


def _find_stop_in_widget():
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
        except Exception:
            pass
    return None


def _btn_count():
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
    except Exception:
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
        safe_id = bundle_id.replace('\\', '\\\\').replace('"', '\\"')
        subprocess.run(['osascript', '-e', f'''
            tell application "System Events"
                try
                    set t to first process whose bundle identifier is "{safe_id}"
                    set frontmost of t to true
                end try
            end tell
        '''], capture_output=True, timeout=3)


def _find_cancel_in_widget():
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
        except Exception:
            pass
    return None


def _force_close():
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
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _btn_count() > 4:
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
        # 0. Close stale widget if any
        if _has_widget():
            _force_close()
            time.sleep(0.3)

        # 1. Open widget (polling)
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
            log("[!] Widget failed to open")
            return

        # 2. Clear input
        _clear_widget()
        time.sleep(0.1)

        # 3. Click mic (cached or search)
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
            log("[!] Mic button not found")
            _force_close()
            return

        _click(mic_x, mic_y)

        # 4. Poll for recording start
        rec_started = False
        for _ in range(15):
            time.sleep(0.05)
            bc = _btn_count()
            if 0 < bc <= 4:
                rec_started = True
                break

        if not rec_started:
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
            log("[!] Recording failed to start")
            _force_close()
            return

        log("[*] Recording...")

        # 5. Wait for Fn release
        deadline = time.time() + 60
        while fn_pressed and time.time() < deadline:
            time.sleep(0.05)

        # 6. Stop (recording may have auto-stopped on silence)
        bc = _btn_count()
        if 0 < bc <= 4:
            stop = _find_stop_in_widget()
            if stop:
                _click(stop[0], stop[1])
            _wait_normal(5)

        # 7. Wait for transcription
        text = ""
        for _ in range(20):
            time.sleep(0.5)
            t = _read_widget_text()
            if t and t.strip():
                text = t.strip()
                break

        # 8. Copy to clipboard and close
        if text:
            _clipboard(text)
            log(f"[+] {text[:80]}{'...' if len(text) > 80 else ''}")
        else:
            log("[-] Empty")

        _force_close()
        time.sleep(0.15)
        _restore_app(prev_app)

    except Exception as e:
        log(f"[!] Error: {e}")
        _force_close()

    finally:
        with state_lock:
            state = "idle"


def event_cb(proxy, etype, event, refcon):
    global fn_pressed, last_fn_time

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


def main():
    log("=" * 40)
    log("  ChatGPT STT — Fn push-to-talk")
    log("=" * 40)

    if subprocess.run(['which', 'cliclick'], capture_output=True).returncode != 0:
        log("[!] brew install cliclick"); sys.exit(1)

    r = subprocess.run(
        ['osascript', '-e', 'tell application "System Events" to get name of every process whose name is "ChatGPT"'],
        capture_output=True, text=True)
    if 'ChatGPT' not in r.stdout:
        log("[!] Start ChatGPT first"); sys.exit(1)

    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap, Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionListenOnly,
        Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged),
        event_cb, None)
    if not tap:
        log("[!] Accessibility permission required"); sys.exit(1)

    src = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
    Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetCurrent(), src, Quartz.kCFRunLoopDefaultMode)
    Quartz.CGEventTapEnable(tap, True)

    log("[*] Fn -> speak -> release -> Cmd+V")
    log("[*] Ctrl+C to quit\n")

    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    try:
        Quartz.CFRunLoopRun()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()

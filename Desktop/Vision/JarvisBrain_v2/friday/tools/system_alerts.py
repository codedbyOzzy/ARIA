"""FRIDAY Proaktif Sistem Uyarilari.

Arka planda 60sn'de bir RAM, CPU ve pil durumunu kontrol eder.
Esik asilinca Windows bildirimi + FRIDAY sesli uyarir.
"""

from __future__ import annotations

import subprocess
import threading
import time

_CHECK_INTERVAL  = 60   # saniye
_RAM_THRESHOLD   = 88   # % — bu esigi gecinke uyar
_CPU_THRESHOLD   = 92   # % — ortalama yuksekse uyar
_BAT_THRESHOLD   = 15   # % — sarj edilmiyorsa uyar

_started         = False
_speak_callbacks: list = []
_last_warned: dict[str, float] = {}   # uyari turu -> son uyari zamani
_COOLDOWN        = 600  # ayni uyariyi en erken 10dk sonra tekrarla


def register_speak_callback(fn) -> None:
    """fn(message: str) — proaktif uyari metni seslendirilecek."""
    if fn not in _speak_callbacks:
        _speak_callbacks.append(fn)


def _notify(message: str) -> None:
    safe = message.replace('"', "'")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Warning; "
        "$n.BalloonTipIcon = 'Warning'; "
        "$n.BalloonTipTitle = 'F.R.I.D.A.Y. Sistem Uyarisi'; "
        f'$n.BalloonTipText = "{safe}"; '
        "$n.Visible = $true; "
        "$n.ShowBalloonTip(8000); "
        "Start-Sleep -Seconds 9; "
        "$n.Dispose()"
    )
    subprocess.Popen(
        ["powershell", "-WindowStyle", "Hidden", "-NonInteractive", "-Command", script],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _speak(message: str) -> None:
    for cb in list(_speak_callbacks):
        try:
            cb(message)
        except Exception as e:
            print(f"[Alerts] Speak callback hatasi: {e}", flush=True)


def _can_warn(key: str) -> bool:
    now = time.time()
    last = _last_warned.get(key, 0)
    if now - last >= _COOLDOWN:
        _last_warned[key] = now
        return True
    return False


def _check_loop() -> None:
    while True:
        time.sleep(_CHECK_INTERVAL)
        try:
            import psutil

            # RAM kontrolu
            ram = psutil.virtual_memory()
            if ram.percent >= _RAM_THRESHOLD and _can_warn("ram"):
                msg = f"RAM kullanimi yuzde {int(ram.percent)} — sistem yavasliyor olabilir."
                _notify(msg)
                _speak(f"Ozan, RAM dolmak uzere, yuzde {int(ram.percent)}. Bazi uygulamalari kapatmani oneririm.")
                print(f"[Alerts] RAM uyarisi: %{ram.percent}", flush=True)

            # Pil kontrolu
            bat = psutil.sensors_battery()
            if bat and not bat.power_plugged and bat.percent <= _BAT_THRESHOLD and _can_warn("battery"):
                msg = f"Pil yuzde {int(bat.percent)} — sarj cihazini tak."
                _notify(msg)
                _speak(f"Ozan, pil yuzde {int(bat.percent)}'de ve sarj edilmiyor. Sarj cihazini takmanı oneririm.")
                print(f"[Alerts] Pil uyarisi: %{bat.percent}", flush=True)

        except Exception as e:
            print(f"[Alerts] Kontrol hatasi: {e}", flush=True)


def start_system_alerts() -> None:
    """Proaktif sistem izlemeyi basalt. Uygulama acilisinda bir kez cagir."""
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_check_loop, daemon=True).start()
    print("[Alerts] Sistem izleme basladi (RAM, pil).", flush=True)

"""FRIDAY Hatırlatıcı Sistemi.

set_reminder    — N dakika sonra hatırlatıcı kur (Windows bildirimi + sesli)
list_reminders  — aktif hatırlatıcıları listele
cancel_reminder — hatırlatıcıyı iptal et

Hatırlatıcılar .friday_reminders.json dosyasına kaydedilir;
uygulama yeniden başlayınca geçmişi henüz ateşlenmemiş olanlar yüklenir.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

_SAVE_FILE = Path(os.environ.get("FRIDAY_REMINDERS_PATH", ".friday_reminders.json"))

@dataclass
class _Reminder:
    id: str
    message: str
    fire_at: datetime
    fired: bool = False


_reminders: list[_Reminder] = []
_lock = threading.Lock()
_checker_started = False
_fire_callbacks: list = []  # fn(message: str) — ateşlenince çağrılır


def register_fire_callback(fn) -> None:
    """Hatırlatıcı ateşlendiğinde çağrılacak fonksiyonu kaydet (örn: FRIDAY sesli söylesin)."""
    if fn not in _fire_callbacks:
        _fire_callbacks.append(fn)


# ── Kalıcılık ─────────────────────────────────────────────────────────────────

def _save() -> None:
    try:
        data = [
            {"id": r.id, "message": r.message,
             "fire_at": r.fire_at.isoformat(), "fired": r.fired}
            for r in _reminders
        ]
        _SAVE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Reminder] Kayit hatasi: {e}", flush=True)


def _load() -> None:
    if not _SAVE_FILE.exists():
        return
    try:
        data = json.loads(_SAVE_FILE.read_text(encoding="utf-8"))
        now = datetime.now()
        for item in data:
            fire_at = datetime.fromisoformat(item["fire_at"])
            # Geçmişte kalmış ama henüz ateşlenmemiş → ateşlenmiş say
            fired = item.get("fired", False) or fire_at < now
            _reminders.append(_Reminder(
                id=item["id"],
                message=item["message"],
                fire_at=fire_at,
                fired=fired,
            ))
    except Exception as e:
        print(f"[Reminder] Yukle hatasi: {e}", flush=True)


# ── Windows bildirimi ─────────────────────────────────────────────────────────

def _send_notification(message: str) -> None:
    safe = message.replace('"', "'")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        "$n.BalloonTipIcon = 'Info'; "
        "$n.BalloonTipTitle = 'F.R.I.D.A.Y.'; "
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


# ── Arka plan kontrol döngüsü ─────────────────────────────────────────────────

def _checker_loop() -> None:
    while True:
        time.sleep(20)
        now = datetime.now()
        fired_any = False
        with _lock:
            for r in _reminders:
                if not r.fired and now >= r.fire_at:
                    r.fired = True
                    fired_any = True
                    _send_notification(r.message)
                    print(f"[Reminder] Ateslendi: {r.message}", flush=True)
                    for cb in list(_fire_callbacks):
                        try:
                            cb(r.message)
                        except Exception as e:
                            print(f"[Reminder] Callback hatasi: {e}", flush=True)
        if fired_any:
            with _lock:
                _save()


def _ensure_checker() -> None:
    global _checker_started
    if not _checker_started:
        _checker_started = True
        _load()
        threading.Thread(target=_checker_loop, daemon=True).start()


# ── Araçlar ───────────────────────────────────────────────────────────────────

def set_reminder(message: str, minutes: int) -> str:
    """
    Belirtilen dakika sonra hatırlatıcı kur. Süresi dolunca hem Windows bildirimi
    çıkar hem de FRIDAY sesli hatırlatır. Hatırlatıcılar uygulama kapanınca
    kaydedilir, bir sonraki açılışta aktif olanlar yüklenir.
    message: hatırlatılacak şey (örn: 'toplantı başlıyor', 'ilacını al')
    minutes: kaç dakika sonra (örn: 30)
    """
    _ensure_checker()
    mins = max(1, int(minutes))
    fire_at = datetime.now() + timedelta(minutes=mins)
    r = _Reminder(id=str(uuid.uuid4())[:8], message=message, fire_at=fire_at)
    with _lock:
        _reminders.append(r)
        _save()
    return (
        f"Hatirlatici kuruldu: '{message}' — "
        f"saat {fire_at.strftime('%H:%M')}'de ({mins} dk sonra). "
        f"ID: {r.id}"
    )


def list_reminders() -> str:
    """Aktif (henüz ateşlenmemiş) hatırlatıcıların listesini göster."""
    _ensure_checker()
    with _lock:
        aktif = [r for r in _reminders if not r.fired]
    if not aktif:
        return "Aktif hatirlatici yok."
    now = datetime.now()
    lines = [f"{len(aktif)} aktif hatirlatici:"]
    for r in aktif:
        kalan = max(0, int((r.fire_at - now).total_seconds() / 60))
        lines.append(
            f"  [{r.id}] '{r.message}' — "
            f"{r.fire_at.strftime('%H:%M')} ({kalan} dk kaldi)"
        )
    return "\n".join(lines)


def cancel_reminder(reminder_id: str) -> str:
    """
    ID'si verilen hatırlatıcıyı iptal et.
    reminder_id: list_reminders ile görülen kısa ID (örn: 'a3f2b1c0')
    """
    _ensure_checker()
    with _lock:
        for r in _reminders:
            if r.id == reminder_id and not r.fired:
                r.fired = True
                _save()
                return f"Hatirlatici iptal edildi: '{r.message}'"
    return f"ID '{reminder_id}' bulunamadi veya zaten ateslennis."


# ── Export ────────────────────────────────────────────────────────────────────

REMINDER_TOOLS = [set_reminder, list_reminders, cancel_reminder]

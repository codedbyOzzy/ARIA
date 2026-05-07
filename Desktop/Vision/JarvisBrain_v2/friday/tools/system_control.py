"""FRIDAY Sistem Kontrol Araçları.

Tier 1:
  - Pencere Yönetimi  : list_windows, focus_window, minimize_window,
                        maximize_window, close_window, set_window_size
  - Process Kontrolü  : list_processes, kill_process, get_process_info
  - Clipboard         : get_clipboard, set_clipboard
  - Sistem Komutları  : lock_screen, sleep_mode, shutdown_computer,
                        restart_computer, cancel_shutdown, empty_recycle_bin
  - PowerShell        : run_powershell
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import subprocess
import time
from typing import Optional

import psutil

# ── Windows API ───────────────────────────────────────────────────────────────

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32  = ctypes.windll.shell32

SW_MINIMIZE  = 6
SW_MAXIMIZE  = 3
SW_RESTORE   = 9
WM_CLOSE     = 0x0010
CF_UNICODETEXT = 13

# ── Pencere yardımcıları ──────────────────────────────────────────────────────

def _enum_windows() -> list[tuple[int, str]]:
    results: list[tuple[int, str]] = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def _cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()
                if title and title != "Program Manager":
                    results.append((hwnd, title))
        return True

    user32.EnumWindows(WNDENUMPROC(_cb), 0)
    return results


def _find_hwnd(query: str) -> tuple[Optional[int], Optional[str]]:
    """Başlığa göre pencere bul — tam eşleşme önce, sonra kısmi."""
    q = query.lower().strip()
    windows = _enum_windows()
    for hwnd, title in windows:
        if title.lower() == q:
            return hwnd, title
    for hwnd, title in windows:
        if q in title.lower():
            return hwnd, title
    return None, None


# ═════════════════════════════════════════════════════════════════════════════
# PENCERE YÖNETİMİ
# ═════════════════════════════════════════════════════════════════════════════

def list_windows() -> str:
    """Şu an açık olan tüm pencereleri listele."""
    windows = _enum_windows()
    if not windows:
        return "Açık pencere bulunamadı."
    lines = [f"{len(windows)} açık pencere:"]
    for i, (_, title) in enumerate(windows, 1):
        lines.append(f"  {i:>2}. {title}")
    return "\n".join(lines)


def focus_window(title: str) -> str:
    """Belirtilen pencereyi öne getir ve odakla.
    title: pencerenin başlığı veya bir kısmı (örn. 'Chrome', 'Excel').
    """
    hwnd, found = _find_hwnd(title)
    if not hwnd:
        return f"'{title}' başlıklı pencere bulunamadı.\n{list_windows()}"
    # Minimize'ysa önce geri getir
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    return f"'{found}' penceresi öne getirildi."


def minimize_window(title: str) -> str:
    """Belirtilen pencereyi küçült (görev çubuğuna al).
    title: pencerenin başlığı veya bir kısmı.
    """
    hwnd, found = _find_hwnd(title)
    if not hwnd:
        return f"'{title}' başlıklı pencere bulunamadı."
    user32.ShowWindow(hwnd, SW_MINIMIZE)
    return f"'{found}' küçültüldü."


def maximize_window(title: str) -> str:
    """Belirtilen pencereyi tam ekran yap.
    title: pencerenin başlığı veya bir kısmı.
    """
    hwnd, found = _find_hwnd(title)
    if not hwnd:
        return f"'{title}' başlıklı pencere bulunamadı."
    user32.ShowWindow(hwnd, SW_MAXIMIZE)
    return f"'{found}' büyütüldü."


def close_window(title: str) -> str:
    """Belirtilen pencereyi kapat. SADECE kullanıcı onayından sonra çağır.
    title: pencerenin başlığı veya bir kısmı.
    """
    hwnd, found = _find_hwnd(title)
    if not hwnd:
        return f"'{title}' başlıklı pencere bulunamadı."
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    return f"'{found}' kapatma sinyali gönderildi."


def set_window_size(title: str, width: int, height: int) -> str:
    """Belirtilen pencerenin boyutunu ayarla.
    title: pencerenin başlığı.
    width: genişlik (piksel).
    height: yükseklik (piksel).
    """
    hwnd, found = _find_hwnd(title)
    if not hwnd:
        return f"'{title}' başlıklı pencere bulunamadı."
    # Mevcut pozisyonu koru, sadece boyutu değiştir
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    user32.MoveWindow(hwnd, rect.left, rect.top, width, height, True)
    return f"'{found}' boyutu {width}x{height} olarak ayarlandı."


# ═════════════════════════════════════════════════════════════════════════════
# PROCESS KONTROLÜ
# ═════════════════════════════════════════════════════════════════════════════

def list_processes(sort_by: str = "memory") -> str:
    """Çalışan süreçleri listele. sort_by: 'memory' veya 'cpu'."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status"]):
        try:
            info = p.info
            mem  = (info["memory_info"].rss / 1024 / 1024) if info["memory_info"] else 0
            procs.append({
                "pid":    info["pid"],
                "name":   info["name"] or "?",
                "cpu":    info["cpu_percent"] or 0.0,
                "mem_mb": mem,
                "status": info["status"],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    key = "cpu" if sort_by.lower() == "cpu" else "mem_mb"
    procs.sort(key=lambda x: x[key], reverse=True)

    lines = [f"{'Isim':<28} {'PID':>6}  {'CPU%':>5}  {'RAM':>8}"]
    lines.append("-" * 55)
    for p in procs[:25]:
        lines.append(
            f"{p['name'][:27]:<28} {p['pid']:>6}  {p['cpu']:>4.1f}%  {p['mem_mb']:>6.0f} MB"
        )
    lines.append(f"\nToplam {len(procs)} süreç çalışıyor.")
    return "\n".join(lines)


def kill_process(name_or_pid: str) -> str:
    """Bir süreci sonlandır. SADECE kullanıcı onayından sonra çağır.
    name_or_pid: süreç adı (örn. 'chrome.exe') veya PID numarası.
    """
    # Sistem süreçlerine dokunma
    PROTECTED = {"system", "smss.exe", "csrss.exe", "wininit.exe",
                 "services.exe", "lsass.exe", "svchost.exe", "winlogon.exe"}

    killed = []
    errors = []

    # PID mi, isim mi?
    target_pid: Optional[int] = None
    try:
        target_pid = int(name_or_pid)
    except ValueError:
        pass

    for p in psutil.process_iter(["pid", "name"]):
        try:
            name = p.info["name"] or ""
            pid  = p.info["pid"]

            if name.lower() in PROTECTED:
                continue

            match = (target_pid is not None and pid == target_pid) or \
                    (target_pid is None and name_or_pid.lower() in name.lower())

            if match:
                p.terminate()
                killed.append(f"{name} (PID {pid})")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            errors.append(str(e))

    if not killed:
        return f"'{name_or_pid}' adıyla çalışan bir süreç bulunamadı."

    result = f"Sonlandırıldı: {', '.join(killed)}"
    if errors:
        result += f"\nHatalar: {'; '.join(errors)}"
    return result


def get_process_info(name: str) -> str:
    """Belirli bir süreç hakkında detaylı bilgi al.
    name: süreç adı veya PID (örn. 'chrome.exe').
    """
    found = []
    try:
        target_pid = int(name)
    except ValueError:
        target_pid = None

    for p in psutil.process_iter(["pid", "name", "exe", "cpu_percent",
                                   "memory_info", "status", "create_time",
                                   "num_threads"]):
        try:
            info = p.info
            pname = info["name"] or ""
            pid   = info["pid"]
            if (target_pid and pid == target_pid) or \
               (not target_pid and name.lower() in pname.lower()):
                mem  = (info["memory_info"].rss / 1024 / 1024) if info["memory_info"] else 0
                uptime = time.time() - (info["create_time"] or time.time())
                h, m  = divmod(int(uptime // 60), 60)
                found.append(
                    f"Ad       : {pname}\n"
                    f"PID      : {pid}\n"
                    f"Durum    : {info['status']}\n"
                    f"RAM      : {mem:.1f} MB\n"
                    f"CPU      : {info['cpu_percent']:.1f}%\n"
                    f"Thread   : {info['num_threads']}\n"
                    f"Calisma  : {h}s {m}dk\n"
                    f"Yol      : {info['exe'] or 'bilinmiyor'}"
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if not found:
        return f"'{name}' adıyla çalışan bir süreç bulunamadı."
    return "\n\n".join(found[:3])


# ═════════════════════════════════════════════════════════════════════════════
# CLIPBOARD
# ═════════════════════════════════════════════════════════════════════════════

def get_clipboard() -> str:
    """Panodaki (clipboard) içeriği oku ve döndür."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-Command", "Get-Clipboard"],
            capture_output=True, timeout=5,
            encoding="utf-8", errors="replace",
        )
        text = (result.stdout or "").strip()
        if not text:
            return "Pano bos veya metin icermiyor."
        preview = text[:800]
        suffix  = f"\n... ({len(text)} karakter toplam)" if len(text) > 800 else ""
        return f"Panodaki icerik:\n{preview}{suffix}"
    except Exception as e:
        return f"Pano okuma hatasi: {e}"


def set_clipboard(text: str) -> str:
    """Metni panoya (clipboard) kopyala.
    text: panoya yazılacak metin.
    """
    try:
        # PowerShell üzerinden daha güvenilir
        escaped = text.replace("'", "''")
        result  = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Set-Clipboard -Value '{escaped}'"],
            capture_output=True, timeout=5,
        )
        if result.returncode == 0:
            preview = text[:80] + ("..." if len(text) > 80 else "")
            return f"Panoya kopyalandı: {preview}"
        return f"Kopyalama hatası: {result.stderr.decode(errors='replace')}"
    except Exception as e:
        return f"Pano yazma hatası: {e}"


# ═════════════════════════════════════════════════════════════════════════════
# SİSTEM KOMUTLARI
# ═════════════════════════════════════════════════════════════════════════════

def lock_screen() -> str:
    """Ekranı kilitle (Windows oturum kilidi)."""
    user32.LockWorkStation()
    return "Ekran kilitleniyor."


def sleep_mode() -> str:
    """Bilgisayarı uyku moduna al."""
    subprocess.Popen(
        ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
        shell=False,
    )
    return "Uyku moduna geçiliyor."


def shutdown_computer(delay_seconds: int = 30) -> str:
    """Bilgisayarı kapat. SADECE kullanıcı açıkça onay verdikten sonra çağır.
    delay_seconds: kaç saniye sonra kapanacak (varsayılan 30).
    """
    delay_seconds = max(0, min(delay_seconds, 3600))
    subprocess.run(["shutdown", "/s", "/t", str(delay_seconds)], check=False)
    return (
        f"Bilgisayar {delay_seconds} saniye sonra kapanacak. "
        "İptal etmek için: cancel_shutdown"
    )


def restart_computer(delay_seconds: int = 30) -> str:
    """Bilgisayarı yeniden başlat. SADECE kullanıcı açıkça onay verdikten sonra çağır.
    delay_seconds: kaç saniye sonra yeniden başlayacak (varsayılan 30).
    """
    delay_seconds = max(0, min(delay_seconds, 3600))
    subprocess.run(["shutdown", "/r", "/t", str(delay_seconds)], check=False)
    return (
        f"Bilgisayar {delay_seconds} saniye sonra yeniden başlayacak. "
        "İptal etmek için: cancel_shutdown"
    )


def cancel_shutdown() -> str:
    """Bekleyen kapatma veya yeniden başlatma işlemini iptal et."""
    result = subprocess.run(
        ["shutdown", "/a"], capture_output=True, text=True, check=False
    )
    if result.returncode == 0:
        return "Kapatma/yeniden başlatma iptal edildi."
    return "İptal edilecek bekleyen bir işlem yok."


def empty_recycle_bin() -> str:
    """Geri dönüşüm kutusunu boşalt. Kullanıcı onayından sonra çağır."""
    SHERB_NOCONFIRMATION = 0x00000001
    SHERB_NOPROGRESSUI   = 0x00000002
    SHERB_NOSOUND        = 0x00000004
    flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
    ret = shell32.SHEmptyRecycleBinW(None, None, flags)
    if ret == 0:
        return "Geri donusum kutusu bosaltildi."
    # 0x80070057 = already empty
    return "Geri donusum kutusu zaten bos."


# ═════════════════════════════════════════════════════════════════════════════
# POWERSHELL ÇALIŞTIRICISI
# ═════════════════════════════════════════════════════════════════════════════

# Tehlikeli pattern'ler — bunları içeren komutları reddet
_PS_BLOCKED = [
    "remove-item.*-recurse.*-force.*c:\\\\",
    "format-volume",
    "clear-disk",
    "set-executionpolicy.*unrestricted",
    "invoke-expression.*downloadstring",
    "iex.*http",
]

import re as _re

def run_powershell(command: str) -> str:
    """PowerShell komutu çalıştır ve çıktısını döndür.
    command: çalıştırılacak PowerShell komutu (örn. 'Get-NetIPAddress', 'Get-Disk').
    Tehlikeli ve yıkıcı komutlar engellenir.
    """
    for pattern in _PS_BLOCKED:
        if _re.search(pattern, command.lower()):
            return f"Guvenlik: Bu komut engellendi."

    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-Command", command,
            ],
            capture_output=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if stderr and not stdout:
            return f"Hata:\n{stderr[:1000]}"
        if stdout:
            # Çıktıyı makul boyutta tut
            lines = stdout.splitlines()
            if len(lines) > 60:
                stdout = "\n".join(lines[:60]) + f"\n... ({len(lines)} satır toplam)"
            return stdout
        return "Komut calisti (cikti yok)."
    except subprocess.TimeoutExpired:
        return "Komut zaman asimina ugradi (30 saniye)."
    except FileNotFoundError:
        return "PowerShell bulunamadi."
    except Exception as e:
        return f"PowerShell hatasi: {e}"


# ── FRIDAY kapanma ───────────────────────────────────────────────────────────

_quit_callback = None  # app_new.py tarafından register edilir


def register_quit_callback(fn) -> None:
    """Qt uygulamasını kapatacak fonksiyonu kaydet."""
    global _quit_callback
    _quit_callback = fn


def shutdown_friday(confirmed: bool) -> str:
    """F.R.I.D.A.Y. uygulamasını kapat.
    SADECE kullanici net olarak 'kapat', 'kapa', 'gule gule', 'gorusuruz', 'cikis' dediginde cagir.
    confirmed=True ile cagirmak zorunludur, aksi halde kapanmaz."""
    if not confirmed:
        return "Kapatmak icin confirmed=True gonder."
    if _quit_callback:
        import threading
        threading.Timer(1.5, _quit_callback).start()
        return "Kapaniyorum. Gorusuruz Ozan."
    return "Kapatma callback'i kayitli degil."


# ── Export ────────────────────────────────────────────────────────────────────

SYSTEM_CONTROL_TOOLS = [
    # Pencere
    list_windows,
    focus_window,
    minimize_window,
    maximize_window,
    close_window,
    set_window_size,
    # Process
    list_processes,
    kill_process,
    get_process_info,
    # Clipboard
    get_clipboard,
    set_clipboard,
    # Sistem
    lock_screen,
    sleep_mode,
    shutdown_computer,
    restart_computer,
    cancel_shutdown,
    empty_recycle_bin,
    # PowerShell
    run_powershell,
    # FRIDAY
    shutdown_friday,
]

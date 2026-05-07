"""Standalone tool callables — Gemini function calling için register edilir.

NOT: from __future__ import annotations KULLANILMAZ.
     Gemini SDK inspect.signature() ile annotation'ları okur;
     __future__ annotations ile bunlar string olur ve isinstance() patlar.
"""

import ctypes
import datetime
import glob as _glob
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

# ── App Cache ──────────────────────────────────────────────────────────────────

_APP_CACHE_FILE = Path(os.getcwd()) / ".friday_app_cache.json"
_APP_CACHE = {}
_APP_CACHE_LOCK = threading.Lock()

_APP_MAP = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"], "calc": ["calc.exe"],
    "cmd": ["cmd.exe"], "terminal": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "explorer": ["explorer.exe"], "dosya gezgini": ["explorer.exe"],
    "settings": ["cmd.exe", "/c", "start", "ms-settings:"],
    "ayarlar": ["cmd.exe", "/c", "start", "ms-settings:"],
    "task manager": ["taskmgr.exe"], "görev yöneticisi": ["taskmgr.exe"],
    "paint": ["mspaint.exe"],
    "chrome": ["cmd.exe", "/c", "start", "chrome"],
    "google chrome": ["cmd.exe", "/c", "start", "chrome"],
    "edge": ["cmd.exe", "/c", "start", "msedge"],
    "microsoft edge": ["cmd.exe", "/c", "start", "msedge"],
    "firefox": ["cmd.exe", "/c", "start", "firefox"],
    "opera": ["cmd.exe", "/c", "start", "opera"],
    "opera gx": ["cmd.exe", "/c", "start", "opera"],
    "discord": ["cmd.exe", "/c", "start", "discord"],
    "slack": ["cmd.exe", "/c", "start", "slack"],
    "teams": ["cmd.exe", "/c", "start", "teams"],
    "zoom": ["cmd.exe", "/c", "start", "zoom"],
    "telegram": ["cmd.exe", "/c", "start", "telegram"],
    "whatsapp": ["cmd.exe", "/c", "start", "whatsapp"],
    "spotify": ["cmd.exe", "/c", "start", "spotify"],
    "steam": ["cmd.exe", "/c", "start", "steam"],
    "vlc": ["cmd.exe", "/c", "start", "vlc"],
    "netflix": ["cmd.exe", "/c", "start", "netflix"],
    "vscode": ["cmd.exe", "/c", "start", "code"],
    "vs code": ["cmd.exe", "/c", "start", "code"],
    "visual studio code": ["cmd.exe", "/c", "start", "code"],
    "code": ["cmd.exe", "/c", "start", "code"],
    "word": ["cmd.exe", "/c", "start", "winword"],
    "excel": ["cmd.exe", "/c", "start", "excel"],
    "powerpoint": ["cmd.exe", "/c", "start", "powerpnt"],
}


def _load_cache():
    global _APP_CACHE
    if _APP_CACHE_FILE.exists():
        try:
            with open(_APP_CACHE_FILE, encoding="utf-8") as f:
                _APP_CACHE = json.load(f)
        except Exception:
            pass


def _scan_registry_apps():
    """Windows Registry'den kurulu uygulamaları tara (DisplayName → InstallLocation)."""
    found = {}
    try:
        import winreg
        keys = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ]
        for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            for key_path in keys:
                try:
                    key = winreg.OpenKey(hive, key_path)
                    count = winreg.QueryInfoKey(key)[0]
                    for i in range(count):
                        try:
                            sub_name = winreg.EnumKey(key, i)
                            sub = winreg.OpenKey(key, sub_name)
                            try:
                                display_name = winreg.QueryValueEx(sub, "DisplayName")[0]
                                name = display_name.strip().lower()
                                # Exe yolunu bul
                                try:
                                    install_loc = winreg.QueryValueEx(sub, "InstallLocation")[0]
                                    if install_loc and os.path.isdir(install_loc):
                                        # Klasördeki ilk .exe'yi bul
                                        for fn in os.listdir(install_loc):
                                            if fn.lower().endswith(".exe") and "uninstall" not in fn.lower():
                                                found[name] = os.path.join(install_loc, fn)
                                                break
                                except Exception:
                                    pass
                                # DisplayIcon alternatif
                                if name not in found:
                                    try:
                                        icon = winreg.QueryValueEx(sub, "DisplayIcon")[0]
                                        if icon and icon.endswith(".exe") and os.path.isfile(icon.split(",")[0]):
                                            found[name] = icon.split(",")[0]
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                        except Exception:
                            pass
                except Exception:
                    pass
    except Exception:
        pass
    return found


def _refresh_cache_bg():
    def _run():
        found = {}
        skip = {"uninstall", "kaldır", "readme", "help", "yardım", "license", "changelog", "update"}

        # 1) Start Menu .lnk tarayıcı
        for root in [
            os.path.join(os.getenv("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(os.getenv("ProgramData", "C:\\ProgramData"), "Microsoft", "Windows", "Start Menu", "Programs"),
        ]:
            if not os.path.isdir(root):
                continue
            for lnk in _glob.glob(os.path.join(root, "**", "*.lnk"), recursive=True):
                name = os.path.splitext(os.path.basename(lnk))[0].lower().strip()
                if not name or any(k in name for k in skip):
                    continue
                if name not in found:
                    found[name] = lnk

        # 2) Registry tabanlı tarayıcı
        reg_apps = _scan_registry_apps()
        for name, path in reg_apps.items():
            if not any(k in name for k in skip) and name not in found:
                found[name] = path

        with _APP_CACHE_LOCK:
            _APP_CACHE.update(found)
        try:
            with open(_APP_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(_APP_CACHE, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


_load_cache()
_refresh_cache_bg()


# ── System Tools ───────────────────────────────────────────────────────────────

def open_application(app_name: str) -> str:
    """Open a Windows desktop application by name (örn: 'spotify', 'chrome', 'notepad', 'discord')."""
    app = (app_name or "").strip().lower()
    if app.endswith(".exe"):
        app = app[:-4]
    if not app:
        return "Uygulama adı boş."

    cmd = _APP_MAP.get(app)

    if cmd is None:
        exe = shutil.which(app) or shutil.which(app + ".exe")
        if exe:
            cmd = [exe]

    if cmd is None:
        with _APP_CACHE_LOCK:
            lnk = _APP_CACHE.get(app)
            if not lnk:
                for k, v in _APP_CACHE.items():
                    if app in k or k in app:
                        lnk = v
                        break
        if lnk:
            cmd = ["cmd.exe", "/c", "start", "", lnk]

    if cmd is None:
        cmd = ["cmd.exe", "/c", "start", "", app_name]

    try:
        subprocess.Popen(cmd, shell=False)
        # GUI uygulamalarının yüklenmesi için bekle
        time.sleep(1.5)
        return app_name + " açıldı ve hazır."
    except Exception as e:
        return app_name + " açılamadı: " + str(e)


def close_application(app_name: str) -> str:
    """Close/kill a running application by name (örn: 'spotify', 'notepad', 'chrome', 'discord')."""
    app = (app_name or "").strip().lower()
    if app.endswith(".exe"):
        app = app[:-4]
    exe_map = {
        "chrome": "chrome.exe", "google chrome": "chrome.exe",
        "edge": "msedge.exe", "microsoft edge": "msedge.exe",
        "firefox": "firefox.exe", "opera": "opera.exe", "opera gx": "opera.exe",
        "notepad": "notepad.exe", "calculator": "calc.exe", "calc": "calc.exe",
        "spotify": "Spotify.exe", "discord": "Discord.exe",
        "steam": "steam.exe", "vlc": "vlc.exe",
        "vscode": "Code.exe", "vs code": "Code.exe", "code": "Code.exe",
        "explorer": "explorer.exe", "dosya gezgini": "explorer.exe",
        "task manager": "Taskmgr.exe", "görev yöneticisi": "Taskmgr.exe",
        "paint": "mspaint.exe", "teams": "Teams.exe",
        "telegram": "Telegram.exe", "whatsapp": "WhatsApp.exe",
        "word": "WINWORD.EXE", "excel": "EXCEL.EXE", "powerpoint": "POWERPNT.EXE",
    }
    exe = exe_map.get(app, app + ".exe")
    result = subprocess.run(
        ["taskkill", "/f", "/im", exe],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return app_name + " kapatıldı."
    # Try without .exe suffix too
    result2 = subprocess.run(
        ["taskkill", "/f", "/im", app],
        capture_output=True, text=True
    )
    if result2.returncode == 0:
        return app_name + " kapatıldı."
    return app_name + " kapatılamadı (zaten kapalı olabilir)."


def create_folder(path: str) -> str:
    """Create a new folder/directory. If only a name is given (e.g. 'Deneme'), creates it on the Desktop.

    Examples: 'Deneme', 'Projeler', 'C:/Users/Pc/Desktop/Notlar'
    """
    p = (path or "").strip()
    if not p:
        return "Klasör adı boş."
    if not os.path.isabs(p) and "\\" not in p and "/" not in p:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        p = os.path.join(desktop, p)
    try:
        os.makedirs(p, exist_ok=True)
        return "Klasör oluşturuldu: " + p
    except Exception as e:
        return "Klasör oluşturulamadı: " + str(e)


def delete_file(path: str) -> str:
    """Delete a file or empty folder. path: full path or filename on Desktop.

    Examples: 'eski_not.txt', 'C:/Users/Pc/Desktop/eski_not.txt'
    """
    p = (path or "").strip()
    if not p:
        return "Dosya yolu boş."
    if not os.path.isabs(p) and "\\" not in p and "/" not in p:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        p = os.path.join(desktop, p)
    try:
        if os.path.isdir(p):
            import shutil as _shutil
            _shutil.rmtree(p)
            return "Klasör silindi: " + p
        elif os.path.isfile(p):
            os.remove(p)
            return "Dosya silindi: " + p
        else:
            return "Bulunamadı: " + p
    except Exception as e:
        return "Silinemedi: " + str(e)


def open_website(url: str) -> str:
    """Open a website in the default browser (örn: 'youtube.com', 'github.com')."""
    u = (url or "").strip()
    if not u:
        return "URL boş."
    if not u.startswith("http://") and not u.startswith("https://"):
        u = "https://" + u
    webbrowser.open(u)
    return "Tarayıcıda açıldı: " + u


def get_current_time() -> str:
    """Get the current date and time."""
    now = datetime.datetime.now().astimezone()
    return now.strftime("Tarih: %d %B %Y, Saat: %H:%M")


def get_system_stats() -> str:
    """Get current CPU, RAM, disk usage and battery status."""
    try:
        import psutil  # type: ignore
    except ImportError:
        return "psutil kurulu değil (pip install psutil)."
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    parts = [
        "CPU: %" + str(round(cpu)),
        "RAM: %" + str(round(ram.percent)) + " (" + str(round(ram.used / 1e9, 1)) + "GB / " + str(round(ram.total / 1e9, 1)) + "GB)",
        "Disk: %" + str(round(disk.percent)),
    ]
    bat = psutil.sensors_battery()
    if bat:
        parts.append("Pil: %" + str(round(bat.percent)) + (" şarj oluyor" if bat.power_plugged else ""))
    return ", ".join(parts)


# ── Weather ────────────────────────────────────────────────────────────────────

def get_weather(location: str) -> str:
    """Get current weather for a city (örn: 'Istanbul', 'Ankara', 'London', 'New York')."""
    loc = (location or "").strip()
    if not loc:
        loc = "Istanbul"
    try:
        url = "https://wttr.in/" + urllib.parse.quote(loc) + "?format=j1"
        with urllib.request.urlopen(url, timeout=6) as resp:  # nosec B310
            data = json.loads(resp.read())
        c = data["current_condition"][0]
        cond = c["weatherDesc"][0]["value"]
        return (
            loc + ": " + c["temp_C"] + "°C, " + cond
            + ", nem %" + c["humidity"]
            + ", rüzgar " + c["windspeedKmph"] + " km/s"
        )
    except Exception as e:
        return "Hava durumu alınamadı (" + loc + "): " + str(e)


# ── Web / News ─────────────────────────────────────────────────────────────────

def _fetch_rss_titles(urls, limit=8):
    titles = []
    for url in urls:
        if len(titles) >= limit:
            break
        try:
            with httpx.Client(timeout=6, follow_redirects=True) as client:
                r = client.get(url, headers={"User-Agent": "Friday-AI/2.0"})
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:3]:
                t = item.findtext("title")
                if t:
                    titles.append(re.sub(r"<[^>]+>", "", t).strip())
        except Exception:
            continue
    return titles


def get_turkish_news() -> str:
    """Get the latest news headlines from Turkish sources (Hürriyet, NTV, Sabah)."""
    feeds = [
        "https://www.hurriyet.com.tr/rss/anasayfa",
        "https://www.ntv.com.tr/son-dakika.rss",
        "https://www.sabah.com.tr/rss/anasayfa.xml",
    ]
    titles = _fetch_rss_titles(feeds, 8)
    if not titles:
        return "Türk haber kaynakları şu an yanıt vermiyor, efendim."
    return "Son dakika Türkiye haberleri: " + " | ".join(titles[:6])


def get_world_news() -> str:
    """Get the latest international news headlines from global sources (BBC, Al Jazeera, NYT)."""
    feeds = [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    ]
    titles = _fetch_rss_titles(feeds, 8)
    if not titles:
        return "Uluslararası haber kaynakları şu an yanıt vermiyor, efendim."
    return "Dünya haberleri: " + " | ".join(titles[:6])


def search_web(query: str) -> str:
    """Search the web for any topic and return a summary of results."""
    try:
        from ddgs import DDGS  # type: ignore
        lines = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                t = str(r.get("title", "")).strip()
                b = str(r.get("body", "")).strip()
                if t:
                    lines.append((t + ". " + b)[:280])
        return " ".join(lines[:3]) if lines else "Sonuç bulunamadı: " + query
    except Exception as e:
        return "Web araması başarısız: " + str(e)


# ── Volume & Media ─────────────────────────────────────────────────────────────

_VK_MUTE = 0xAD
_VK_VOL_DOWN = 0xAE
_VK_VOL_UP = 0xAF
_VK_NEXT = 0xB0
_VK_PREV = 0xB1
_VK_STOP = 0xB2
_VK_PLAY = 0xB3


def _vkey(vk, n=1):
    user32 = ctypes.windll.user32
    for _ in range(n):
        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.04)
        user32.keybd_event(vk, 0, 0x0002, 0)


def set_volume(level: int) -> str:
    """Set the system volume to a specific percentage between 0 and 100."""
    pct = max(0, min(100, int(level or 0)))
    try:
        from pycaw.pycaw import AudioUtilities  # type: ignore
        vol = AudioUtilities.GetSpeakers().EndpointVolume
        vol.SetMasterVolumeLevelScalar(pct / 100.0, None)
        return "Ses seviyesi %" + str(pct) + " olarak ayarlandı."
    except Exception:
        return "Ses seviyesi %" + str(pct) + " ayarlanamadı."


def volume_up(steps: int) -> str:
    """Increase the system volume by a number of steps (each step is about 2 percent)."""
    n = max(1, min(20, int(steps or 5)))
    _vkey(_VK_VOL_UP, n)
    return "Ses " + str(n) + " adım artırıldı."


def volume_down(steps: int) -> str:
    """Decrease the system volume by a number of steps."""
    n = max(1, min(20, int(steps or 5)))
    _vkey(_VK_VOL_DOWN, n)
    return "Ses " + str(n) + " adım azaltıldı."


def mute_volume() -> str:
    """Toggle mute on the system audio output."""
    _vkey(_VK_MUTE)
    return "Ses kapatıldı/açıldı."


def get_volume() -> str:
    """Get the current system volume level as a percentage."""
    try:
        from pycaw.pycaw import AudioUtilities  # type: ignore
        vol = AudioUtilities.GetSpeakers().EndpointVolume
        pct = round(vol.GetMasterVolumeLevelScalar() * 100)
        return "Ses seviyesi şu an %" + str(pct) + "."
    except Exception:
        return "Ses seviyesi okunamadı."


def media_play_pause() -> str:
    """Play or pause the currently active media player (Spotify, YouTube, VLC, etc.)."""
    _vkey(_VK_PLAY)
    return "Oynat/Duraklat."


def media_next() -> str:
    """Skip to the next track in the active media player."""
    _vkey(_VK_NEXT)
    return "Sonraki parça."


def media_prev() -> str:
    """Go to the previous track in the active media player."""
    _vkey(_VK_PREV)
    return "Önceki parça."


# ── All tools list (used by brain.py) ─────────────────────────────────────────

from friday.tools.desktop import DESKTOP_TOOLS
from friday.tools.memory_tools import MEMORY_TOOLS
from friday.tools.filesystem import FILESYSTEM_TOOLS
from friday.tools.system_control import SYSTEM_CONTROL_TOOLS
from friday.tools.browser_automation import BROWSER_TOOLS
from friday.tools.steam_tools import STEAM_TOOLS
from friday.tools.reminder import REMINDER_TOOLS
from friday.tools.quick_notes import QUICK_NOTE_TOOLS

ALL_TOOLS = [
    open_application,
    close_application,
    create_folder,
    delete_file,
    open_website,
    get_current_time,
    get_system_stats,
    get_weather,
    get_turkish_news,
    get_world_news,
    search_web,
    set_volume,
    volume_up,
    volume_down,
    mute_volume,
    get_volume,
    media_play_pause,
    media_next,
    media_prev,
] + DESKTOP_TOOLS + MEMORY_TOOLS + FILESYSTEM_TOOLS + SYSTEM_CONTROL_TOOLS + BROWSER_TOOLS + STEAM_TOOLS + REMINDER_TOOLS + QUICK_NOTE_TOOLS

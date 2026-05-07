"""Steam automation tools for FRIDAY.

steam_open_library   — Steam kütüphanesini aç
steam_list_installed — Bilgisayarda yüklü Steam oyunlarını listele
steam_launch_game    — Yüklü bir oyunu isimle aç (steam://rungameid)
steam_search_game    — Steam'de oyun ara, fiyat/bilgi göster
steam_install_game   — Oyunu bul, AppID'yi al, kurulum ekranını aç + disk önerisi
get_disk_space_info  — Tüm sürücülerin boş alanını listele
"""

import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path


# ── Lokal Steam kütüphanesi okuyucu ──────────────────────────────────────────

def _get_steam_root() -> Path | None:
    """Steam kurulum klasörünü bul."""
    candidates = [
        Path(r"C:\Program Files (x86)\Steam"),
        Path(r"C:\Program Files\Steam"),
        Path(os.environ.get("ProgramFiles(x86)", ""), "Steam"),
    ]
    # Registry'den de dene
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\WOW6432Node\Valve\Steam")
        path = winreg.QueryValueEx(key, "InstallPath")[0]
        if path:
            candidates.insert(0, Path(path))
    except Exception:
        pass
    for p in candidates:
        if p.exists():
            return p
    return None


def _get_library_paths() -> list[Path]:
    """Tüm Steam kütüphane klasörlerini döndür (ana + ek sürücüler)."""
    root = _get_steam_root()
    if not root:
        return []

    libraries = [root / "steamapps"]

    # libraryfolders.vdf okuyarak ek kütüphaneleri bul
    vdf = root / "steamapps" / "libraryfolders.vdf"
    if not vdf.exists():
        vdf = root / "config" / "libraryfolders.vdf"

    if vdf.exists():
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace")
            # "path"  "D:\\SteamLibrary" formatını yakala
            for m in re.finditer(r'"path"\s+"([^"]+)"', text):
                p = Path(m.group(1).replace("\\\\", "\\")) / "steamapps"
                if p.exists() and p not in libraries:
                    libraries.append(p)
        except Exception:
            pass

    return libraries


def _parse_acf(path: Path) -> dict | None:
    """Tek bir appmanifest_*.acf dosyasını parse et."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        appid = re.search(r'"appid"\s+"(\d+)"', text)
        name  = re.search(r'"name"\s+"([^"]+)"', text)
        state = re.search(r'"StateFlags"\s+"(\d+)"', text)
        if appid and name:
            flags = int(state.group(1)) if state else 0
            # StateFlags 4 = tam kurulu, diğerleri indirme/güncelleme
            installed = (flags & 4) != 0 or flags == 0
            return {
                "appid": appid.group(1),
                "name":  name.group(1),
                "installed": installed,
            }
    except Exception:
        pass
    return None


def _get_installed_games() -> dict[str, dict]:
    """
    Yüklü tüm oyunları döndür.
    Sonuç: {normalized_name: {"appid": "...", "name": "..."}}
    """
    games = {}
    for lib in _get_library_paths():
        for acf in lib.glob("appmanifest_*.acf"):
            info = _parse_acf(acf)
            if info and info["installed"]:
                key = info["name"].lower().strip()
                games[key] = {"appid": info["appid"], "name": info["name"]}
    return games


def _normalize(s: str) -> str:
    """Boşluk, noktalama, sürüm ekleri kaldır."""
    s = s.lower()
    s = re.sub(r"[^a-z0-9]", "", s)  # sadece harf+rakam
    return s


# Yaygın kısaltmalar → Steam adı parçası
_ABBREV = {
    "cs2": "counter-strike 2",
    "csgo": "counter-strike",
    "cs": "counter-strike",
    "gta5": "grand theft auto v",
    "gta": "grand theft auto",
    "pubg": "battlegrounds",
    "lol": "league of legends",
    "wow": "world of warcraft",
    "rdr2": "red dead redemption 2",
    "ef": "efootball",
}


def _find_game_local(query: str, games: dict) -> dict | None:
    """Oyun adına göre esnek arama."""
    q = query.lower().strip()

    # Kısaltma varsa genişlet
    expanded = _ABBREV.get(q, q)

    # 1) Tam eşleşme
    if q in games:
        return games[q]

    # 2) Kısaltma genişletilmişse tekrar dene
    if expanded != q:
        for key, info in games.items():
            if expanded in key or key in expanded:
                return info

    # 3) Kısmi eşleşme (sorgu oyun adında geçiyor ya da tersi)
    for key, info in games.items():
        if q in key or key in q:
            return info

    # 4) Normalize edip karşılaştır (noktalama/boşluk farkı yok say)
    qn = _normalize(q)
    for key, info in games.items():
        kn = _normalize(key)
        if qn in kn or kn in qn:
            return info

    # 5) Kelime bazlı — sorgunun kelimelerinden en az biri eşleşiyorsa
    words = q.split()
    best, best_score = None, 0
    for key, info in games.items():
        score = sum(1 for w in words if len(w) > 2 and w in key)
        if score > best_score:
            best_score = score
            best = info
    return best if best_score >= 1 else None


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _steam_api_search(name: str) -> dict | None:
    """Steam Store Search API — ilk uygulama sonucunu döndür."""
    url = (
        "https://store.steampowered.com/api/storesearch/"
        "?term=" + urllib.parse.quote(name)
        + "&l=turkish&cc=TR"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        items = data.get("items", [])
        # Önce "app" tipini tercih et (DLC/bundle değil)
        apps = [i for i in items if i.get("type") == "app"]
        return apps[0] if apps else (items[0] if items else None)
    except Exception:
        return None


def _disk_summary() -> tuple[list[str], str]:
    """(satır listesi, en iyi sürücü açıklaması) döndür."""
    lines: list[str] = []
    best_drive = ""
    best_free  = 0
    try:
        import shutil
        import psutil
        for part in psutil.disk_partitions():
            mp = part.mountpoint
            if not mp:
                continue
            try:
                usage   = shutil.disk_usage(mp)
                free_gb = usage.free  / (1024 ** 3)
                tot_gb  = usage.total / (1024 ** 3)
                lines.append(f"  {mp}: {free_gb:.1f} GB bos / {tot_gb:.1f} GB toplam")
                if usage.free > best_free:
                    best_free  = usage.free
                    best_drive = f"{mp} ({free_gb:.1f} GB bos)"
            except Exception:
                pass
    except Exception:
        pass
    return lines, best_drive


def _open_steam_url(steam_url: str) -> bool:
    """steam:// protokolünü aç. True dönerse başarılı."""
    try:
        os.startfile(steam_url)
        return True
    except Exception:
        pass
    # Fallback: Steam executable
    for exe in [
        r"C:\Program Files (x86)\Steam\steam.exe",
        r"C:\Program Files\Steam\steam.exe",
    ]:
        if os.path.exists(exe):
            subprocess.Popen([exe, steam_url])
            return True
    return False


# ── Araçlar ───────────────────────────────────────────────────────────────────

def steam_open_library() -> str:
    """Steam kütüphanesini aç (Steam zaten açıksa kütüphane sekmesine geç)."""
    if _open_steam_url("steam://open/games"):
        return "Steam kutuphanesi aciliyor."
    return "Steam acilamadi. Kurulu mu kontrol edin."


def steam_list_installed() -> str:
    """Bilgisayarda yüklü olan tüm Steam oyunlarını listele."""
    games = _get_installed_games()
    if not games:
        return "Yüklü Steam oyunu bulunamadı (Steam kurulu olmayabilir veya kütüphane okunamadı)."
    lines = [f"{len(games)} yüklü oyun:"]
    for info in sorted(games.values(), key=lambda x: x["name"].lower()):
        lines.append(f"  • {info['name']}  (AppID: {info['appid']})")
    return "\n".join(lines)


def steam_launch_game(game_name: str) -> str:
    """Bilgisayarda yüklü bir Steam oyununu ismiyle başlat.
    Önce lokal kütüphanede arar, bulamazsa Steam Store'da arar.
    game_name: oyun adı (örn. 'cs2', 'cyberpunk', 'elden ring', 'gta 5')
    """
    name = (game_name or "").strip()
    if not name:
        return "Oyun adı belirtmediniz."

    # Önce lokalde ara
    games = _get_installed_games()
    info = _find_game_local(name, games)

    if info:
        app_id = info["appid"]
        title  = info["name"]
        if _open_steam_url(f"steam://rungameid/{app_id}"):
            return f"'{title}' başlatılıyor."
        return f"'{title}' başlatılamadı (AppID: {app_id})."

    # Lokalde yoksa bildir + Store'da ara
    item = _steam_api_search(name)
    if item:
        title  = item.get("name", name)
        app_id = item.get("id")
        return (
            f"'{name}' bilgisayarında yüklü değil.\n"
            f"Steam Store'da bulundu: {title} (AppID: {app_id})\n"
            f"Kurmak ister misin?"
        )
    return f"'{name}' ne lokalde ne de Steam Store'da bulunamadı."


def steam_search_game(game_name: str) -> str:
    """Steam'de oyun ara ve bilgilerini (fiyat, AppID, mağaza linki) göster. Kurulum başlatmaz."""
    name = (game_name or "").strip()
    if not name:
        return "Oyun adı belirtmediniz."

    item = _steam_api_search(name)
    if not item:
        return f"'{name}' Steam'de bulunamadi."

    app_id = item.get("id", "?")
    title  = item.get("name", name)
    price  = item.get("price", {})

    lines = [f"Oyun: {title}", f"AppID: {app_id}"]
    if price:
        final    = price.get("final", 0) / 100
        currency = price.get("currency", "TRY")
        lines.append(f"Fiyat: {final:.2f} {currency}")
    lines.append(f"Magaza: https://store.steampowered.com/app/{app_id}")
    return "\n".join(lines)


def steam_install_game(game_name: str) -> str:
    """Steam'de oyun ara, AppID'yi bul ve kurulum ekranını ac. En bos diski de onerir."""
    name = (game_name or "").strip()
    if not name:
        return "Oyun adı belirtmediniz."

    disk_lines, best_drive = _disk_summary()

    item = _steam_api_search(name)
    if not item:
        _open_steam_url("steam://open/games")
        msg = f"'{name}' Steam'de bulunamadi. Kutüphane acildi, manuel arayabilirsin."
        if best_drive:
            msg += f"\n\nDisk durumu:\n" + "\n".join(disk_lines)
        return msg

    app_id = item.get("id")
    title  = item.get("name", name)

    install_url = f"steam://install/{app_id}"
    if _open_steam_url(install_url):
        msg = f"'{title}' kurulum ekrani aciliyor (AppID: {app_id})."
    else:
        msg = f"'{title}' bulunamadi (AppID: {app_id}). Steam'i manuel acin."

    if disk_lines:
        msg += "\n\nDisk durumu:\n" + "\n".join(disk_lines)
        if best_drive:
            msg += f"\n  => En fazla bos alan: {best_drive}"

    return msg


def get_disk_space_info() -> str:
    """Bilgisayardaki tüm sürücülerin boş ve toplam disk alanını göster."""
    lines, best = _disk_summary()
    if not lines:
        return "Disk bilgisi alinamadi."
    result = "Disk Durumu:\n" + "\n".join(lines)
    if best:
        result += f"\n  => En fazla bos: {best}"
    return result


# ── Export ────────────────────────────────────────────────────────────────────

STEAM_TOOLS = [
    steam_open_library,
    steam_list_installed,
    steam_launch_game,
    steam_search_game,
    steam_install_game,
    get_disk_space_info,
]

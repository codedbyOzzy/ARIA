"""FRIDAY Dosya Sistemi Araçları.

find_file, list_folder, read_file, rename_file, move_file,
copy_file, delete_file_safe, get_file_info
"""

from __future__ import annotations

import os
import shutil
import stat
from datetime import datetime
from pathlib import Path

# ── Arama kökleri (öncelik sırasıyla) ────────────────────────────────────────

_SEARCH_ROOTS = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Downloads",
    Path.home() / "OneDrive",
    Path.home() / "OneDrive" / "Desktop",
    Path.home() / "OneDrive" / "Documents",
    Path.home(),
]

_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
    ".csv", ".html", ".css", ".xml", ".ini", ".cfg", ".log",
    ".bat", ".ps1", ".sh", ".env", ".toml",
}

_MAX_RESULTS   = 10
_MAX_READ_CHARS = 4000


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _resolve(path: str) -> Path:
    """Kullanıcıdan gelen path'i çöz — ~ ve relatif yolları destekle."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        # Göreceli yolu masaüstüne göre dene, sonra home'a
        for root in (Path.home() / "Desktop", Path.home()):
            candidate = root / p
            if candidate.exists():
                return candidate
        return Path.home() / p
    return p


def _fmt_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 ** 2:
        return f"{size/1024:.1f} KB"
    if size < 1024 ** 3:
        return f"{size/1024**2:.1f} MB"
    return f"{size/1024**3:.1f} GB"


def _fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%d %b %Y %H:%M")


# ── Araçlar ───────────────────────────────────────────────────────────────────

def find_file(name: str, where: str = "") -> str:
    """
    Dosya veya klasörü ada ya da pattern'e göre ara.
    where: aranacak klasör (boş bırakılırsa Desktop, Documents, Downloads, home taranır).
    Glob pattern destekler: *.pdf, rapor*, *2025*.docx
    """
    name = name.strip()
    if not name:
        return "Aranacak isim belirtmediniz."

    roots: list[Path] = []
    if where:
        roots = [_resolve(where)]
    else:
        roots = [r for r in _SEARCH_ROOTS if r.exists()]

    # Tam eşleşme önce, sonra pattern
    pattern = name if any(c in name for c in ("*", "?", "[")) else f"*{name}*"

    found: list[Path] = []
    seen: set[Path]   = set()

    for root in roots:
        try:
            for match in root.rglob(pattern):
                if match in seen:
                    continue
                seen.add(match)
                found.append(match)
                if len(found) >= _MAX_RESULTS:
                    break
        except PermissionError:
            pass
        if len(found) >= _MAX_RESULTS:
            break

    if not found:
        return f"'{name}' adında bir dosya/klasör bulunamadı."

    lines = [f"{len(found)} sonuç bulundu:"]
    for i, p in enumerate(found, 1):
        try:
            st   = p.stat()
            size = _fmt_size(st.st_size) if p.is_file() else "klasör"
            date = _fmt_time(st.st_mtime)
            lines.append(f"{i}. {p}  [{size}, {date}]")
        except Exception:
            lines.append(f"{i}. {p}")

    return "\n".join(lines)


def list_folder(path: str) -> str:
    """
    Klasör içeriğini listele.
    path: listelenmek istenen klasör yolu (boş bırakılırsa Desktop gösterilir).
    """
    target = _resolve(path) if path.strip() else Path.home() / "Desktop"

    if not target.exists():
        return f"'{target}' bulunamadı."
    if not target.is_dir():
        return f"'{target}' bir klasör değil, dosya."

    try:
        items = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return f"'{target}' klasörüne erişim izni yok."

    if not items:
        return f"'{target}' klasörü boş."

    folders = [p for p in items if p.is_dir()]
    files   = [p for p in items if p.is_file()]

    lines = [f"[{target}]  ({len(folders)} klasor, {len(files)} dosya)"]

    if folders:
        lines.append("\nKlasorler:")
        for p in folders[:30]:
            lines.append(f"  [K] {p.name}/")

    if files:
        lines.append("\nDosyalar:")
        for p in files[:50]:
            try:
                st = p.stat()
                lines.append(f"  [D] {p.name}  [{_fmt_size(st.st_size)}, {_fmt_time(st.st_mtime)}]")
            except Exception:
                lines.append(f"  [D] {p.name}")

    return "\n".join(lines)


def read_file(path: str) -> str:
    """
    Metin dosyasının içeriğini oku ve döndür.
    path: okunacak dosyanın tam yolu veya adı.
    """
    target = _resolve(path)

    if not target.exists():
        # Bulunamazsa arama yap
        results = find_file(target.name)
        return f"'{target}' bulunamadı.\n{results}"

    if target.is_dir():
        return f"'{target}' bir klasör. Dosya yolu belirtin."

    if target.suffix.lower() not in _TEXT_EXTENSIONS:
        return (
            f"'{target.name}' metin dosyası değil ({target.suffix}). "
            "Sadece .txt, .md, .py, .json vb. dosyalar okunabilir."
        )

    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except PermissionError:
        return f"'{target}' dosyasına erişim izni yok."
    except Exception as e:
        return f"Okuma hatası: {e}"

    if len(text) > _MAX_READ_CHARS:
        text = text[:_MAX_READ_CHARS] + f"\n... (dosya {len(text)} karakter, ilk {_MAX_READ_CHARS} gösteriliyor)"

    return f"--- {target.name} ---\n{text}"


def rename_file(path: str, new_name: str) -> str:
    """
    Dosya veya klasörü yeniden adlandır.
    path: mevcut dosya/klasör yolu veya adı.
    new_name: yeni ad (sadece ad, yol değil).
    """
    target = _resolve(path)

    if not target.exists():
        # Arama yap
        return f"'{path}' bulunamadı. Lütfen tam yolu belirtin veya önce find_file ile arayın."

    new_name = new_name.strip()
    if not new_name:
        return "Yeni isim boş olamaz."

    # Yolu koruyarak yeni adı oluştur
    destination = target.parent / new_name

    if destination.exists():
        return f"'{new_name}' zaten mevcut. Farklı bir isim seçin."

    try:
        target.rename(destination)
        return f"✓ '{target.name}' → '{new_name}' olarak yeniden adlandırıldı.\nYeni yol: {destination}"
    except PermissionError:
        return f"'{target}' için yeniden adlandırma izni yok."
    except Exception as e:
        return f"Yeniden adlandırma hatası: {e}"


def move_file(path: str, destination: str) -> str:
    """
    Dosya veya klasörü taşı.
    path: taşınacak dosya/klasör yolu.
    destination: hedef klasör yolu veya tam yol.
    """
    src = _resolve(path)
    dst = _resolve(destination)

    if not src.exists():
        return f"'{path}' bulunamadı."

    # Hedef bir klasörse dosyayı içine taşı
    if dst.is_dir():
        dst = dst / src.name

    if dst.exists():
        return f"Hedefte '{dst.name}' zaten mevcut. Önce yeniden adlandırın."

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"✓ '{src.name}' → '{dst}' konumuna taşındı."
    except PermissionError:
        return f"Taşıma için yetki yok."
    except Exception as e:
        return f"Taşıma hatası: {e}"


def copy_file(path: str, destination: str) -> str:
    """
    Dosya veya klasörü kopyala.
    path: kopyalanacak dosya/klasör.
    destination: hedef klasör veya tam yol.
    """
    src = _resolve(path)
    dst = _resolve(destination)

    if not src.exists():
        return f"'{path}' bulunamadı."

    if dst.is_dir():
        dst = dst / src.name

    if dst.exists():
        return f"Hedefte '{dst.name}' zaten mevcut."

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))
        size = _fmt_size(dst.stat().st_size) if dst.is_file() else ""
        return f"✓ '{src.name}' → '{dst}' olarak kopyalandı.{' ' + size if size else ''}"
    except PermissionError:
        return "Kopyalama için yetki yok."
    except Exception as e:
        return f"Kopyalama hatası: {e}"


def delete_file_safe(path: str) -> str:
    """
    Dosya veya klasörü sil. SADECE kullanıcı açıkça onay verdikten sonra çağır.
    path: silinecek dosya/klasörün tam yolu (find_file sonucundan alınan).
    """
    target = _resolve(path)

    if not target.exists():
        return f"'{path}' bulunamadı veya zaten silinmiş."

    name = target.name
    try:
        if target.is_dir():
            shutil.rmtree(str(target))
            return f"✓ '{name}' klasörü ve içeriği silindi."
        else:
            size = _fmt_size(target.stat().st_size)
            target.unlink()
            return f"✓ '{name}' ({size}) silindi."
    except PermissionError:
        # Sistem dosyalarına dokunmaya çalışıyorsa
        try:
            os.chmod(str(target), stat.S_IWRITE)
            target.unlink()
            return f"✓ '{name}' silindi (salt-okunur bayrağı kaldırıldı)."
        except Exception:
            return f"'{name}' silinemedi — sistem dosyası veya yetki yok."
    except Exception as e:
        return f"Silme hatası: {e}"


def get_file_info(path: str) -> str:
    """
    Dosya veya klasör hakkında detaylı bilgi göster (boyut, oluşturma tarihi, değiştirilme tarihi, tür).
    path: incelenecek dosya/klasör yolu veya adı.
    """
    target = _resolve(path)

    if not target.exists():
        results = find_file(target.name)
        return f"'{path}' bulunamadı.\n{results}"

    try:
        st = target.stat()
    except Exception as e:
        return f"Bilgi alınamadı: {e}"

    lines = [f"[Dosya] {target.name}" if target.is_file() else f"[Klasor] {target.name}"]
    lines.append(f"Tam yol   : {target}")
    lines.append(f"Tür       : {'Dosya' if target.is_file() else 'Klasör'} ({target.suffix or 'uzantısız'})")

    if target.is_file():
        lines.append(f"Boyut     : {_fmt_size(st.st_size)}")

    lines.append(f"Oluşturulma: {_fmt_time(st.st_ctime)}")
    lines.append(f"Değiştirilme: {_fmt_time(st.st_mtime)}")
    lines.append(f"Son erişim: {_fmt_time(st.st_atime)}")

    if target.is_dir():
        try:
            children = list(target.iterdir())
            n_files   = sum(1 for c in children if c.is_file())
            n_folders = sum(1 for c in children if c.is_dir())
            lines.append(f"İçerik    : {n_files} dosya, {n_folders} klasör")
        except Exception:
            pass

    return "\n".join(lines)


# ── Export ────────────────────────────────────────────────────────────────────

FILESYSTEM_TOOLS = [
    find_file,
    list_folder,
    read_file,
    rename_file,
    move_file,
    copy_file,
    delete_file_safe,
    get_file_info,
]

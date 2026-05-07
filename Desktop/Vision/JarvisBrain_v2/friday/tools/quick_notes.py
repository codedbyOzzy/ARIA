"""FRIDAY Hizli Not Sistemi.

take_note   — Desktop'taki FRIDAY_notlar.txt dosyasina timestamp ile not ekle
read_notes  — notlari oku
clear_notes — tum notlari temizle (onay gerektirir)
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

_NOTES_FILE = Path.home() / "Desktop" / "FRIDAY_notlar.txt"


def take_note(content: str) -> str:
    """
    Bir notu kalici olarak kaydet. 'Not al: ...', 'Bunu not et: ...' komutlarinda kullan.
    Notlar masaustu'ndeki FRIDAY_notlar.txt dosyasina eklenir.
    content: kaydedilecek not metni
    """
    content = (content or "").strip()
    if not content:
        return "Not icerigi bos."

    timestamp = datetime.now().strftime("[%d %b %Y %H:%M]")
    line = f"{timestamp} {content}\n"

    try:
        with open(_NOTES_FILE, "a", encoding="utf-8") as f:
            f.write(line)
        return f"Not kaydedildi: '{content}'"
    except Exception as e:
        return f"Not kaydedilemedi: {e}"


def read_notes() -> str:
    """Kaydedilen tum notlari oku ve listele."""
    if not _NOTES_FILE.exists():
        return "Henuz kayitli not yok."

    try:
        text = _NOTES_FILE.read_text(encoding="utf-8").strip()
        if not text:
            return "Not dosyasi bos."
        lines = text.splitlines()
        return f"{len(lines)} not:\n" + "\n".join(lines[-20:])  # son 20
    except Exception as e:
        return f"Notlar okunamadi: {e}"


def clear_notes(confirmed: bool) -> str:
    """
    Not listesini temizle.
    confirmed=False -> kac not oldugunu say, kullanicidan onay iste, confirmed=True ile tekrar cagir.
    confirmed=True  -> notlari sil.
    confirmed: kullanici onayladi mi (True/False)
    """
    if not _NOTES_FILE.exists():
        return "Silinecek not yok."
    try:
        lines = [l for l in _NOTES_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
        count = len(lines)
    except Exception as e:
        return f"Notlar okunamadi: {e}"

    if not confirmed:
        return f"{count} not var. Hepsini silmemi istiyor musun? Onayliyorsan bana 'evet' de."

    try:
        _NOTES_FILE.unlink()
        return f"{count} not silindi."
    except Exception as e:
        return f"Notlar silinemedi: {e}"


QUICK_NOTE_TOOLS = [take_note, read_notes, clear_notes]

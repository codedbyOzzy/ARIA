"""FRIDAY hafıza araçları — Gemini'nin çağırabileceği remember/recall/forget fonksiyonları."""

from __future__ import annotations


def _store():
    from friday.memory import get_memory_store
    return get_memory_store()


# ── Araçlar ───────────────────────────────────────────────────────────────────

def remember_this(content: str) -> str:
    """Bir şeyi kalıcı olarak hafızaya kaydet. Ozan seni bir şeyi hatırlamanı istediğinde kullan."""
    from friday.memory import MemoryCategory
    mid = _store().store(content, category=MemoryCategory.FACT, importance=0.8)
    if mid:
        return f"Hatırladım: {content}"
    return "Zaten hafızamda var."


def recall_memory(query: str) -> str:
    """Hafızandan ilgili bilgileri geri çağır. 'Geçen hafta ne konuştuk', 'bunu söylemiş miydim', 'beni hatırlıyor musun' gibi sorularda kullan."""
    return _store().recall_as_text(query, top_k=8)


def forget_memory(content: str) -> str:
    """Belirtilen konuyla ilgili hafıza kaydını sil. Ozan bir şeyi unutmanı istediğinde kullan."""
    return _store().forget_by_content(content)


def memory_stats() -> str:
    """Hafıza sisteminin istatistiklerini göster (kaç kayıt var, kategoriler vb.)"""
    s = _store().stats()
    lines = [f"Toplam hafıza: {s['total']}"]
    for cat, count in s.get("categories", {}).items():
        lines.append(f"  {cat}: {count}")
    lines.append(f"Ortalama önem: {s.get('avg_importance', 0):.2f}")
    return "\n".join(lines)


MEMORY_TOOLS = [remember_this, recall_memory, forget_memory, memory_stats]

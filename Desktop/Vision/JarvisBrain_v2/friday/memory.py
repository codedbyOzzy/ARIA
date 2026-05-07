"""FRIDAY Persistent Memory System.

Neural-AI-Memory-System'den ilham alınarak FRIDAY'e özel tasarlandı.

Mimari:
  - 5 kategori: PREFERENCE, FACT, EVENT, GOAL, CONTEXT
  - JSON kalıcı depolama (.friday_memory.json)
  - TF-IDF cosine benzerlik + önem + güncellik ağırlıklı geri çağırma
  - Her konuşma turu sonrası Gemini Flash ile otomatik hafıza çıkarımı
  - Decay (çürüme) + Reinforce (güçlendirme) lifecycle yönetimi
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


# ── Konfigürasyon ─────────────────────────────────────────────────────────────

MEMORY_PATH        = Path(os.environ.get("FRIDAY_MEMORY_PATH", ".friday_memory.json"))
EXTRACT_MODEL      = os.environ.get("OPENAI_LLM_MODEL", "gpt-4.1-mini")  # hafıza çıkarımı
MAX_CONTEXT_ITEMS  = 20                    # system prompt'a max kaç hafıza enjekte edilsin


# ── Veri yapıları ─────────────────────────────────────────────────────────────

class MemoryCategory(str, Enum):
    PREFERENCE = "preference"   # Ozan'ın tercihleri, sevdikleri/sevmedikleri
    FACT       = "fact"         # Ozan hakkında öğrenilen gerçekler
    EVENT      = "event"        # Gerçekleşen olaylar / geçmiş konuşmalar
    GOAL       = "goal"         # Ozan'ın hedefleri ve planları
    CONTEXT    = "context"      # Genel bağlam / proje bilgileri


@dataclass
class Memory:
    id:            str
    content:       str
    category:      MemoryCategory
    importance:    float      = 0.5
    created_at:    float      = field(default_factory=time.time)
    last_accessed: float      = field(default_factory=time.time)
    access_count:  int        = 0
    tags:          list       = field(default_factory=list)
    embedding:     list[float] = field(default_factory=list)   # semantic vector

    def age_days(self) -> float:
        return (time.time() - self.last_accessed) / 86400

    def touch(self, reinforce: float = 0.05):
        self.last_accessed = time.time()
        self.access_count += 1
        self.importance = min(1.0, self.importance + reinforce)


# ── Ana sınıf ─────────────────────────────────────────────────────────────────

class MemoryStore:
    """FRIDAY'in beyin hafızası."""

    # Lifecycle — uzun dönem hafıza için yavaş decay
    DECAY_PER_DAY      = 0.004   # çok yavaş çürüme: 0.8 önemli hafıza ~200 günde sıfırlanır
    PRUNE_THRESHOLD    = 0.02    # çok düşük eşik: sadece gerçekten eskimiş kayıtlar silinir
    REINFORCE_INC      = 0.05    # her erişimde önem artışı

    # Retrieval ağırlıkları (toplamı 1.0 olmalı)
    W_RELEVANCE  = 0.50
    W_IMPORTANCE = 0.30
    W_RECENCY    = 0.20
    HALF_LIFE    = 30.0   # gün — 30 günde recency 0.5'e düşer (eski: 14)

    def __init__(self, path: Path = MEMORY_PATH):
        self._path     = Path(path)
        self._store: dict[str, Memory] = {}
        self._dirty    = False
        self._load()

    # ── Kalıcılık ─────────────────────────────────────────────────────────────

    def _load(self):
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for item in raw:
                try:
                    cat = MemoryCategory(item.get("category", "fact"))
                except ValueError:
                    cat = MemoryCategory.FACT
                m = Memory(
                    id=item["id"],
                    content=item["content"],
                    category=cat,
                    importance=float(item.get("importance", 0.5)),
                    created_at=float(item.get("created_at", time.time())),
                    last_accessed=float(item.get("last_accessed", time.time())),
                    access_count=int(item.get("access_count", 0)),
                    tags=list(item.get("tags", [])),
                    embedding=list(item.get("embedding", [])),
                )
                self._store[m.id] = m
            print(f"[Memory] {len(self._store)} hafıza yüklendi.", flush=True)
        except Exception as e:
            print(f"[Memory] Yükleme hatası: {e}", flush=True)

    def _save(self):
        try:
            data = [
                {
                    "id":            m.id,
                    "content":       m.content,
                    "category":      m.category.value,
                    "importance":    round(m.importance, 4),
                    "created_at":    m.created_at,
                    "last_accessed": m.last_accessed,
                    "access_count":  m.access_count,
                    "tags":          m.tags,
                    "embedding":     m.embedding,
                }
                for m in self._store.values()
            ]
            self._path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._dirty = False
        except Exception as e:
            print(f"[Memory] Kayıt hatası: {e}", flush=True)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def store(
        self,
        content:    str,
        category:   MemoryCategory = MemoryCategory.FACT,
        importance: float           = 0.5,
        tags:       list[str]       = None,
    ) -> str:
        """Yeni bir hafıza kaydeder, ID döndürür."""
        content = content.strip()
        if not content:
            return ""

        # Çok benzer bir kayıt zaten varsa güncelle, yenisini ekleme
        existing = self._find_duplicate(content)
        if existing:
            existing.importance = min(1.0, max(existing.importance, importance))
            existing.touch(reinforce=0.0)
            self._save()
            print(f"[Memory] Güncellendi (duplicate): {content[:60]}", flush=True)
            return existing.id

        m = Memory(
            id=str(uuid.uuid4()),
            content=content,
            category=category,
            importance=max(0.0, min(1.0, importance)),
            tags=tags or [],
            embedding=_embed(content),   # semantic vector
        )
        self._store[m.id] = m
        self._save()
        print(f"[Memory] Yeni [{category.value}]: {content[:80]}", flush=True)
        return m.id

    def forget(self, memory_id: str) -> bool:
        if memory_id in self._store:
            del self._store[memory_id]
            self._save()
            return True
        return False

    def forget_by_content(self, query: str) -> str:
        """En alakalı hafızayı içeriğe göre sil."""
        results = self.recall(query, top_k=1)
        if not results:
            return "Silinecek bir şey bulamadım."
        m, score = results[0]
        if score < 0.1:
            return "Silinecek bir şey bulamadım."
        self.forget(m.id)
        return f"Silindi: {m.content}"

    def get(self, memory_id: str) -> Optional[Memory]:
        return self._store.get(memory_id)

    def count(self) -> int:
        return len(self._store)

    # ── Geri çağırma ─────────────────────────────────────────────────────────

    def recall(
        self,
        query:    str,
        top_k:    int                       = 6,
        category: Optional[MemoryCategory]  = None,
    ) -> list[tuple[Memory, float]]:
        """
        Sorguya göre hafızaları puanlar ve sıralar.
        Embedding mevcut ise semantic cosine similarity, yoksa TF-IDF fallback.
        Returns: [(Memory, final_score), ...]
        """
        pool = list(self._store.values())
        if category:
            pool = [m for m in pool if m.category == category]
        if not pool:
            return []

        now = time.time()

        # Semantic embedding: önce query embedding'i dene
        q_embedding = _embed(query)

        # TF-IDF fallback corpus (embedding'siz hafızalar için)
        corpus = [m.content for m in pool]
        q_vec  = _tfidf(query, corpus)

        results = []
        backfill_needed = []   # embedding'i olmayan ama backfill yapılabilecek hafızalar

        for m in pool:
            # Relevance: ikisinde de embedding varsa semantic, yoksa TF-IDF
            if q_embedding and m.embedding:
                relevance = _cosine_vec(q_embedding, m.embedding)
            else:
                relevance = _cosine(q_vec, _tfidf(m.content, corpus))
                if q_embedding and not m.embedding:
                    backfill_needed.append(m)  # lazy backfill kuyruğu

            importance = m.importance
            age_d      = (now - m.last_accessed) / 86400
            recency    = math.exp(-math.log(2) * age_d / self.HALF_LIFE)
            score      = (
                self.W_RELEVANCE  * relevance +
                self.W_IMPORTANCE * importance +
                self.W_RECENCY    * recency
            )
            results.append((m, score))

        results.sort(key=lambda x: x[1], reverse=True)
        top = results[:top_k]

        # Erişilen hafızaları güçlendir
        for m, _ in top:
            m.touch(self.REINFORCE_INC)

        # Lazy backfill: en fazla 5 eski hafızanın embedding'ini sessizce doldur
        if backfill_needed:
            backfill_needed.sort(key=lambda m: m.importance, reverse=True)
            for m in backfill_needed[:5]:
                vec = _embed(m.content)
                if vec:
                    m.embedding = vec

        if top or backfill_needed:
            self._save()

        return top

    def recall_as_text(self, query: str, top_k: int = 5) -> str:
        results = self.recall(query, top_k=top_k)
        if not results:
            return "Bu konuyla ilgili hafızamda bir şey yok."
        lines = []
        for m, score in results:
            lines.append(f"- [{m.category.value}] {m.content}")
        return "Hafızamda bulunanlar:\n" + "\n".join(lines)

    # ── Context prompt ────────────────────────────────────────────────────────

    def get_context_prompt(
        self,
        max_items: int = MAX_CONTEXT_ITEMS,
        query:     str = "",
    ) -> str:
        """
        System prompt'a enjekte edilecek hafıza bloğunu döndürür.
        query verilirse EVENT/CONTEXT hafızaları konuya göre filtrelenir.
        Zaman dilimine + kategoriye göre gruplandırılmış format.
        """
        if not self._store:
            return ""

        now     = time.time()
        DAY     = 86400

        # ── Tüm hafızaları önem×güncellik skoruyla sırala ──────────────────────
        scored = sorted(
            self._store.values(),
            key=lambda m: m.importance * math.exp(
                -math.log(2) * (now - m.last_accessed) / (DAY * self.HALF_LIFE)
            ),
            reverse=True,
        )

        # ── Kalıcı profil (PREFERENCE + FACT + GOAL) — zaman bağımsız ─────────
        profile = [m for m in scored
                   if m.category in (MemoryCategory.PREFERENCE,
                                     MemoryCategory.FACT,
                                     MemoryCategory.GOAL)][:20]

        # ── Oturum geçmişi (EVENT + CONTEXT) — query varsa alakalı önce gelsin ─
        sessions_pool = [m for m in scored
                         if m.category in (MemoryCategory.EVENT, MemoryCategory.CONTEXT)]

        if query.strip() and sessions_pool:
            # Sorguya göre skor hesapla: embedding varsa semantic, yoksa TF-IDF
            q_embedding = _embed(query)
            corpus = [m.content for m in sessions_pool]
            q_vec  = _tfidf(query, corpus)
            ranked = []
            for m in sessions_pool:
                if q_embedding and m.embedding:
                    rel = _cosine_vec(q_embedding, m.embedding)
                else:
                    rel = _cosine(q_vec, _tfidf(m.content, corpus))
                age_d = (now - m.last_accessed) / DAY
                rec   = math.exp(-math.log(2) * age_d / self.HALF_LIFE)
                score = 0.5 * rel + 0.3 * m.importance + 0.2 * rec
                ranked.append((m, score))
            ranked.sort(key=lambda x: x[1], reverse=True)
            sessions = [m for m, _ in ranked]
        else:
            sessions = sessions_pool

        def _bucket(m: Memory) -> str:
            age = (now - m.created_at) / DAY
            if age < 1:      return "Bugün"
            if age < 7:      return "Bu hafta"
            if age < 14:     return "Geçen hafta"
            if age < 30:     return "Bu ay"
            if age < 60:     return "Geçen ay"
            months = int(age / 30)
            return f"{months} ay önce"

        by_bucket: dict[str, list[Memory]] = {}
        for m in sessions[:max_items]:
            by_bucket.setdefault(_bucket(m), []).append(m)

        bucket_order = ["Bugün", "Bu hafta", "Geçen hafta", "Bu ay",
                        "Geçen ay"] + [k for k in by_bucket
                                       if k not in ("Bugün","Bu hafta",
                                                     "Geçen hafta","Bu ay","Geçen ay")]

        lines = ["[HAFIZA — Ozan hakkında bildiklerin:]"]

        # Profil bölümü
        if profile:
            by_cat: dict[MemoryCategory, list[Memory]] = {}
            for m in profile:
                by_cat.setdefault(m.category, []).append(m)
            _labels = {
                MemoryCategory.PREFERENCE: "Tercihler & Alışkanlıklar",
                MemoryCategory.FACT:       "Bilgiler",
                MemoryCategory.GOAL:       "Hedefler & Planlar",
            }
            lines.append("\nProfil:")
            for cat, label in _labels.items():
                items = by_cat.get(cat, [])
                if items:
                    lines.append(f"  {label}:")
                    for m in items:
                        lines.append(f"    • {m.content}")

        # Geçmiş oturumlar bölümü
        if by_bucket:
            lines.append("\nGeçmiş Konuşmalar (zaman sırasıyla):")
            for bucket in bucket_order:
                items = by_bucket.get(bucket, [])
                if items:
                    lines.append(f"  [{bucket}]")
                    for m in items:
                        lines.append(f"    • {m.content}")

        lines.append("")
        return "\n".join(lines)

    # ── Otomatik çıkarım ──────────────────────────────────────────────────────

    async def extract_from_turn(self, user_text: str, ai_text: str):
        """
        Konuşma turundan kalıcı hafıza çıkarır.
        GPT-4.1-mini'ye gönderilir, JSON yanıt parse edilir.
        Arka planda çalışır — hataları yutmaz, sadece loglar.
        """
        if not user_text and not ai_text:
            return

        prompt = (
            "Aşağıdaki konuşma turunu analiz et ve Ozan hakkında öğrenilen "
            "bilgileri kaydet.\n\n"
            f"Ozan: {user_text}\n"
            f"FRIDAY: {ai_text}\n\n"
            "KAYDET:\n"
            "- Ozan'ın tercihleri, sevdikleri, sevmedikleri (preference)\n"
            "- Ozan hakkında kişisel bilgiler: meslek, ilgi alanları, alışkanlıklar (fact)\n"
            "- Ozan'ın bahsettiği olaylar, yaptığı şeyler (event)\n"
            "- Ozan'ın hedefleri ve planları (goal)\n"
            "- Proje veya bağlam bilgileri (context)\n"
            "- Ozan'ın sorduğu önemli sorular veya merak ettiği konular (context)\n\n"
            "KAYDETME:\n"
            "- Sadece selamlama ('merhaba', 'nasılsın')\n"
            "- FRIDAY'in kendi işleyişiyle ilgili meta sorular\n"
            "- Tek kelimelik anlamsız ifadeler\n\n"
            "Her kayıt TEK net cümle. Kategori seç: preference / fact / event / goal / context\n"
            "Önem: 0.3=düşük, 0.6=orta, 0.8=yüksek, 1.0=kritik\n\n"
            "Eğer kaydedilecek hiçbir şey yoksa boş liste döndür: []\n"
            "SADECE JSON döndür, açıklama ekleme:\n"
            '[{"content":"...","category":"...","importance":0.0,"tags":["..."]}]'
        )

        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=EXTRACT_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=512,
                ),
            )
            text = (response.choices[0].message.content or "").strip()

            # Code fence varsa temizle
            text = re.sub(r'```(?:json)?\s*', '', text).strip()
            text = re.sub(r'```\s*$', '', text).strip()

            # İlk [ ile son ] arasını al (greedy — iç içe içerik güvenli)
            start = text.find('[')
            end   = text.rfind(']')
            if start == -1 or end == -1 or end <= start:
                return

            items = json.loads(text[start:end + 1])
            for item in items:
                content = (item.get("content") or "").strip()
                if not content:
                    continue
                try:
                    cat = MemoryCategory(item.get("category", "fact"))
                except ValueError:
                    cat = MemoryCategory.FACT
                importance = float(item.get("importance", 0.5))
                tags       = list(item.get("tags") or [])
                self.store(content, cat, importance, tags)

        except Exception as e:
            print(f"[Memory] Çıkarım hatası: {e}", flush=True)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def run_decay(self):
        """Eski/erişilmemiş hafızaların önemini azalt, eşiğin altındakileri sil."""
        now      = time.time()
        deleted  = []
        for m in list(self._store.values()):
            age = (now - m.last_accessed) / 86400
            m.importance -= self.DECAY_PER_DAY * age
            if m.importance < self.PRUNE_THRESHOLD:
                deleted.append(m.id)
        for mid in deleted:
            del self._store[mid]
        self._save()
        print(
            f"[Memory] Decay tamamlandı: {len(deleted)} silindi, "
            f"{len(self._store)} kaldı.",
            flush=True,
        )

    # ── Yardımcılar ───────────────────────────────────────────────────────────

    def _find_duplicate(self, content: str, threshold: float = 0.88) -> Optional[Memory]:
        """Çok benzer içerikli mevcut hafızayı bul (duplicate önleme)."""
        if not self._store:
            return None
        corpus = [m.content for m in self._store.values()]
        q_vec  = _tfidf(content, corpus)
        for m in self._store.values():
            sim = _cosine(q_vec, _tfidf(m.content, corpus))
            if sim >= threshold:
                return m
        return None

    def stats(self) -> dict:
        cats = {}
        for m in self._store.values():
            cats[m.category.value] = cats.get(m.category.value, 0) + 1
        return {
            "total":      len(self._store),
            "categories": cats,
            "avg_importance": (
                sum(m.importance for m in self._store.values()) / len(self._store)
                if self._store else 0.0
            ),
        }


# ── Embedding yardımcıları ────────────────────────────────────────────────────

_embed_client = None
_EMBED_MODEL  = "text-embedding-3-small"


def _get_embed_client():
    global _embed_client
    if _embed_client is None:
        try:
            from openai import OpenAI
            _embed_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        except Exception:
            pass
    return _embed_client


def _embed(text: str) -> list[float]:
    """OpenAI text-embedding-3-small ile embedding üret. Hata olursa boş döner."""
    client = _get_embed_client()
    if not client or not text.strip():
        return []
    try:
        resp = client.embeddings.create(model=_EMBED_MODEL, input=text[:2000])
        return resp.data[0].embedding
    except Exception as e:
        print(f"[Memory] Embedding hatası: {e}", flush=True)
        return []


def _cosine_vec(a: list[float], b: list[float]) -> float:
    """İki float vektörü arasında cosine benzerliği."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot  = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ── TF-IDF yardımcıları (saf Python, ekstra bağımlılık yok) ──────────────────

def _tokenize(text: str) -> list[str]:
    return re.findall(r'\b\w+\b', text.lower())


def _tfidf(text: str, corpus: list[str]) -> dict[str, float]:
    tokens = _tokenize(text)
    if not tokens:
        return {}

    tf: dict[str, float] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    n = len(tokens)
    tf = {k: v / n for k, v in tf.items()}

    N = len(corpus) + 1
    vec: dict[str, float] = {}
    for t, tf_val in tf.items():
        df  = sum(1 for doc in corpus if t in _tokenize(doc)) + 1
        idf = math.log(N / df)
        vec[t] = tf_val * idf

    return vec


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys  = set(a) & set(b)
    dot   = sum(a[k] * b[k] for k in keys)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ── Global singleton (tüm modüller aynı store'u paylaşır) ─────────────────────

_global_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    global _global_store
    if _global_store is None:
        _global_store = MemoryStore()
    return _global_store

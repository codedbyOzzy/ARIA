"""Browser automation tools for FRIDAY.

youtube_search  — YouTube arama sonuçlarını varsayılan tarayıcıda aç
youtube_play    — Playwright ile ilk uygun videoyu bul, varsayılan tarayıcıda oynat
google_search   — Google araması yap
"""

import urllib.parse
import webbrowser


def youtube_search(query: str) -> str:
    """YouTube'da arama yap ve sonuçları tarayıcıda aç. Kullanıcı sonuçlar arasından seçim yapabilir."""
    q = (query or "").strip()
    if not q:
        return "Arama terimi belirtmediniz."
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q)
    webbrowser.open(url)
    return f"YouTube'da '{q}' arama sonuçları açıldı."


def youtube_play(query: str) -> str:
    """YouTube'da video ara ve ilk uygun sonucu (reklam/Shorts değil) varsayılan tarayıcıda otomatik oynat."""
    q = (query or "").strip()
    if not q:
        return "Video adı belirtmediniz."

    search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q)

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(search_url, wait_until="domcontentloaded", timeout=15000)

                try:
                    page.wait_for_selector("ytd-video-renderer a#video-title", timeout=10000)
                except Exception:
                    browser.close()
                    webbrowser.open(search_url)
                    return f"YouTube'da '{q}' arama sonuçları açıldı (video listesi yüklenemedi)."

                # Reklam ve Shorts'u atla — ilk gerçek video
                video_url   = None
                video_title = q
                for el in page.query_selector_all("ytd-video-renderer a#video-title")[:8]:
                    href  = el.get_attribute("href") or ""
                    title = el.get_attribute("title") or ""
                    if "/watch?v=" in href:
                        video_url   = "https://www.youtube.com" + href
                        video_title = title
                        break
            finally:
                browser.close()

        if video_url:
            webbrowser.open(video_url)
            return f"'{video_title}' YouTube'da oynatılıyor."
        else:
            webbrowser.open(search_url)
            return f"'{q}' için YouTube arama sonuçları açıldı (otomatik seçim yapılamadı)."

    except ImportError:
        # Playwright kurulu değil — en azından arama sayfasını aç
        webbrowser.open(search_url)
        return (
            f"YouTube'da '{q}' arama sonuçları açıldı. "
            "Otomatik oynatma için: pip install playwright && playwright install chromium"
        )
    except Exception as exc:
        webbrowser.open(search_url)
        return f"YouTube arama sonuçları açıldı. (Hata: {exc})"


def google_search(query: str) -> str:
    """Google'da arama yap ve sonuçları varsayılan tarayıcıda aç."""
    q = (query or "").strip()
    if not q:
        return "Arama terimi belirtmediniz."
    url = "https://www.google.com/search?q=" + urllib.parse.quote(q)
    webbrowser.open(url)
    return f"Google'da '{q}' arama sonuçları açıldı."


BROWSER_TOOLS = [youtube_search, youtube_play, google_search]

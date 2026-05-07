"""Desktop control tools — pyautogui + Gemini vision.

Gemini bu araçları kullanarak:
- Klavyeye yazar / kısayol tuşu basar
- Ekranı görür ve elementlere tıklar
- Not defteri açıp metin yazıp kaydeder
- Steam gibi uygulamaları UI üzerinden kontrol eder
"""

import io
import json
import os
import re
import time

import pyautogui  # type: ignore

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05


def type_text(text: str) -> str:
    """Type text at the current cursor position in any application. Use this to write into Notepad, search boxes, etc."""
    time.sleep(0.2)
    pyautogui.write(str(text), interval=0.04)
    return "'" + str(text)[:40] + ("..." if len(str(text)) > 40 else "") + "' yazıldı."


def press_key(key_combo: str) -> str:
    """Press a keyboard key or shortcut. Examples: 'enter', 'ctrl+s', 'ctrl+a', 'alt+f4', 'escape', 'tab', 'ctrl+c', 'ctrl+v'."""
    keys = [k.strip() for k in str(key_combo).split("+")]
    pyautogui.hotkey(*keys)
    return str(key_combo) + " tuşuna basıldı."


def click_at(x: int, y: int) -> str:
    """Click the mouse at specific screen pixel coordinates (x, y)."""
    pyautogui.click(int(x), int(y))
    return "(" + str(x) + ", " + str(y) + ") koordinatına tıklandı."


def right_click_at(x: int, y: int) -> str:
    """Right-click the mouse at specific screen pixel coordinates (x, y)."""
    pyautogui.rightClick(int(x), int(y))
    return "(" + str(x) + ", " + str(y) + ") sağ tıklandı."


def wait_seconds(seconds: int) -> str:
    """Wait for a number of seconds before continuing (useful after opening an app to let it load)."""
    n = max(1, min(30, int(seconds or 2)))
    time.sleep(n)
    return str(n) + " saniye beklendi."


def scroll(direction: str, amount: int) -> str:
    """Scroll the mouse wheel. direction: 'up' or 'down'. amount: number of scroll steps."""
    n = max(1, min(20, int(amount or 3)))
    clicks = n if str(direction).lower() == "up" else -n
    pyautogui.scroll(clicks)
    return "Kaydırıldı: " + str(direction) + " " + str(n) + " adım."


_VISION_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]


def _gemini_vision(image_bytes, prompt):
    """Send screenshot to Gemini vision. Tries multiple models with one retry each."""
    from google import genai
    from google.genai import types
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
    client = genai.Client(api_key=api_key)
    contents = [
        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
        types.Part.from_text(text=prompt),
    ]
    last_err = ""
    for model in _VISION_MODELS:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(model=model, contents=contents)
                return resp.text or ""
            except Exception as e:
                last_err = str(e)
                print(f"[Vision] {model} deneme {attempt+1} hata: {e}", flush=True)
                if attempt == 0:
                    time.sleep(2)
    return f"Ekran goruntusu alinamadi (tum modeller denendi): {last_err[:120]}"


def look_at_screen(question: str) -> str:
    """Take a screenshot and use AI vision to answer a question about what is currently on the screen."""
    img = pyautogui.screenshot()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    prompt = "Bu ekran görüntüsü hakkında şunu söyle: " + str(question) + " Kısa ve net Türkçe cevap ver."
    return _gemini_vision(buf.getvalue(), prompt)


def find_and_click(element_description: str) -> str:
    """Take a screenshot, find a UI element by description (button, input box, menu item, etc.), and click on it.

    Examples: 'Save button', 'search box', 'File menu', 'close button', 'Install button'
    """
    img = pyautogui.screenshot()
    w, h = img.size
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    prompt = (
        "Ekran görüntüsünde şu elementi bul: '" + str(element_description) + "'\n"
        "Ekran boyutu: " + str(w) + "x" + str(h) + " piksel.\n"
        "SADECE JSON formatında yanıt ver, başka hiçbir şey yazma:\n"
        '{"x": <merkez_x_piksel>, "y": <merkez_y_piksel>, "found": true}\n'
        "Element yoksa: " + '{"x": 0, "y": 0, "found": false}'
    )

    result = _gemini_vision(buf.getvalue(), prompt)

    try:
        match = re.search(r"\{[^}]+\}", result)
        if match:
            data = json.loads(match.group())
            if data.get("found"):
                x, y = int(data["x"]), int(data["y"])
                # Koordinatların ekran sınırları içinde olduğunu kontrol et
                x = max(0, min(x, w - 1))
                y = max(0, min(y, h - 1))
                time.sleep(0.2)
                pyautogui.click(x, y)
                return "'" + str(element_description) + "' bulundu ve (" + str(x) + ", " + str(y) + ") koordinatına tıklandı."
            else:
                return "'" + str(element_description) + "' ekranda bulunamadı."
    except Exception as e:
        return "Element arama hatası: " + str(e)

    return "'" + str(element_description) + "' bulunamadı."


def write_text_file(filename: str, content: str) -> str:
    """Write text content directly to a file. This is the BEST way to save notes and text.

    filename: just the filename with extension (e.g. 'notum.txt', 'liste.txt')
              OR a full path (e.g. 'C:/Users/Pc/Desktop/notum.txt')
    content:  the text to write into the file

    Files are saved to the Desktop by default if only a filename is given.
    Use this INSTEAD of the save dialog for reliable file creation.
    """
    path = str(filename)
    # Sadece dosya adı verilmişse masaüstüne kaydet
    if not os.path.isabs(path) and "\\" not in path and "/" not in path:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        path = os.path.join(desktop, path)
    # Klasörü oluştur
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(content))
    return "Dosya oluşturuldu: " + path


def open_and_write_file(filename: str, content: str) -> str:
    """Open Notepad, display the content visually, AND save it to a file — all in one step.

    filename: filename or full path (default: Desktop)
    content:  text to display and save
    """
    # Önce dosyayı doğrudan kaydet (güvenilir yol)
    write_result = write_text_file(filename, content)

    # Sonra Notepad'de görsel olarak göster
    try:
        import subprocess
        path = str(filename)
        if not os.path.isabs(path) and "\\" not in path and "/" not in path:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            path = os.path.join(desktop, path)
        subprocess.Popen(["notepad.exe", path], shell=False)
    except Exception:
        pass

    return write_result + " ve Notepad'de açıldı."


def save_file_dialog(filepath: str) -> str:
    """In an open Save dialog, type a file path and confirm. Use after pressing Ctrl+S in an app.

    For creating text files, prefer write_text_file() — it's more reliable.
    Only use this when you specifically need to save through a GUI save dialog.
    """
    import subprocess
    # Windows 11 modern dialog için: dialog pencere başlığını bul ve filename alanına yaz
    time.sleep(1.2)  # Dialog'un açılması için bekle

    # Alt+D ile adres çubuğuna git (bazı Windows dialog'larında çalışır)
    # Sonra filename alanını tab ile bul
    # En güvenilir yol: doğrudan pyautogui ile yaz
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.15)
    # Windows path formatına çevir
    win_path = str(filepath).replace("/", "\\")
    pyautogui.write(win_path, interval=0.04)
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(0.5)
    return "Kayıt dialogu tamamlandı: " + str(filepath)


# ── Desktop tool list (actions.py tarafından import edilir) ────────────────────

DESKTOP_TOOLS = [
    type_text,
    press_key,
    click_at,
    right_click_at,
    wait_seconds,
    scroll,
    look_at_screen,
    find_and_click,
    write_text_file,
    open_and_write_file,
    save_file_dialog,
]

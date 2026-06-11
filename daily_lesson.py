"""
Daily lesson script — called by GitHub Actions cron.
Sends a lesson + quiz to all active subscribers via Telegram HTTP API directly.
Does NOT use python-telegram-bot polling; uses requests for stateless one-shot execution.
"""

import os
import json
import requests
import logging

import database as db
from hsk_words import get_word_at_index, get_all_words
from content_generator import generate_lesson, generate_quiz_options

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
    """Send a plain text message to a chat."""
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if not resp.ok:
            logger.error("sendMessage failed for %s: %s", chat_id, resp.text)
            return False
        return True
    except requests.RequestException as e:
        logger.error("sendMessage exception for %s: %s", chat_id, e)
        return False


def send_voice(chat_id: int, word: dict) -> bool:
    """Send TTS pronunciation audio for a Chinese word."""
    import tempfile
    from gtts import gTTS
    # Speak hanzi in Chinese, then pinyin in Vietnamese
    tts_text = f"{word['hanzi']}，{word['pinyin']}"
    tts = gTTS(text=tts_text, lang='zh-cn', slow=True)
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
        tmp_path = f.name
    try:
        tts.save(tmp_path)
        url = f"{TELEGRAM_API}/sendVoice"
        with open(tmp_path, 'rb') as audio:
            resp = requests.post(url, data={"chat_id": chat_id}, files={"voice": audio}, timeout=30)
        if not resp.ok:
            logger.error("sendVoice failed for %s: %s", chat_id, resp.text)
            return False
        return True
    except Exception as e:
        logger.error("sendVoice exception for %s: %s", chat_id, e)
        return False
    finally:
        import os as _os
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass


def _get_cjk_font(size: int = 160):
    """Return a PIL ImageFont for CJK characters, downloading Noto if needed."""
    from PIL import ImageFont
    import tempfile, os as _os

    # Check system fonts first (Windows)
    system_fonts = [
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\msyh.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJKsc-Regular.otf",
    ]
    for fp in system_fonts:
        if _os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue

    # Download Noto Sans CJK SC from Google Fonts CDN to temp
    noto_cache = _os.path.join(tempfile.gettempdir(), "NotoSansSC-Regular.ttf")
    if not _os.path.exists(noto_cache):
        font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/SubsetOTF/SC/NotoSansSC-Regular.otf"
        try:
            r = requests.get(font_url, timeout=60)
            if r.ok:
                with open(noto_cache, "wb") as f:
                    f.write(r.content)
        except Exception as e:
            logger.warning("Font download failed: %s", e)
    if _os.path.exists(noto_cache):
        try:
            return ImageFont.truetype(noto_cache, size)
        except Exception:
            pass
    return None


def send_stroke_order(chat_id: int, word: dict) -> bool:
    """Send a character card image (large hanzi on white background) as a photo."""
    import tempfile, os as _os
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.warning("Pillow not installed; skipping stroke order image")
        return False

    hanzi = word['hanzi']
    char = hanzi[0]

    # Build a 300x300 white card with the character centered
    img_size = 300
    img = Image.new("RGB", (img_size, img_size), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    font = _get_cjk_font(180)
    if font is None:
        logger.warning("No CJK font available; skipping stroke order image")
        return False

    # Center the character
    try:
        bbox = draw.textbbox((0, 0), char, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (img_size - text_w) // 2 - bbox[0]
        y = (img_size - text_h) // 2 - bbox[1]
    except AttributeError:
        # Older Pillow
        text_w, text_h = draw.textsize(char, font=font)
        x = (img_size - text_w) // 2
        y = (img_size - text_h) // 2

    draw.text((x, y), char, fill=(30, 30, 30), font=font)

    # Add a light grid to suggest stroke guidance
    grid_color = (220, 220, 220)
    mid = img_size // 2
    draw.line([(mid, 0), (mid, img_size)], fill=grid_color, width=1)
    draw.line([(0, mid), (img_size, mid)], fill=grid_color, width=1)
    draw.rectangle([0, 0, img_size - 1, img_size - 1], outline=(180, 180, 180), width=2)

    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        tmp_path = f.name
    try:
        img.save(tmp_path, "PNG")
        url = f"{TELEGRAM_API}/sendPhoto"
        with open(tmp_path, 'rb') as img_file:
            resp = requests.post(
                url,
                data={"chat_id": chat_id, "caption": f"✍️ Han tu hom nay: {char} ({word['pinyin']})"},
                files={"photo": img_file},
                timeout=30,
            )
        if not resp.ok:
            logger.warning("sendPhoto character card failed for %s: %s", chat_id, resp.text)
            return False
        return True
    except Exception as e:
        logger.error("sendPhoto character card exception for %s: %s", chat_id, e)
        return False
    finally:
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass


def send_quiz(chat_id: int, word: dict, all_words: list) -> bool:
    """Send a quiz inline keyboard message."""
    quiz_data = generate_quiz_options(word, all_words)
    options = quiz_data["options"]
    correct_idx = quiz_data["correct_idx"]
    labels = ["A", "B", "C", "D"]

    def truncate(text: str, max_len: int = 20) -> str:
        return text if len(text) <= max_len else text[:max_len - 1] + "…"

    inline_keyboard = [
        [
            {"text": f"{labels[0]}: {truncate(options[0])}", "callback_data": f"quiz_{word['hanzi']}_{correct_idx}_0"},
            {"text": f"{labels[1]}: {truncate(options[1])}", "callback_data": f"quiz_{word['hanzi']}_{correct_idx}_1"},
        ],
        [
            {"text": f"{labels[2]}: {truncate(options[2])}", "callback_data": f"quiz_{word['hanzi']}_{correct_idx}_2"},
            {"text": f"{labels[3]}: {truncate(options[3])}", "callback_data": f"quiz_{word['hanzi']}_{correct_idx}_3"},
        ],
    ]

    quiz_text = (
        f"❓ <b>Quiz:</b> Chữ <b>{word['hanzi']}</b> ({word['pinyin']}) — HSK {word['hsk_level']}\n"
        f"Nghĩa là gì?"
    )

    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": quiz_text,
        "parse_mode": "HTML",
        "reply_markup": json.dumps({"inline_keyboard": inline_keyboard}),
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if not resp.ok:
            logger.error("sendQuiz failed for %s: %s", chat_id, resp.text)
            return False
        return True
    except requests.RequestException as e:
        logger.error("sendQuiz exception for %s: %s", chat_id, e)
        return False


def process_subscriber(sub: dict, all_words: list):
    """Send daily lesson + quiz to a single subscriber."""
    chat_id = sub["chat_id"]
    level = sub.get("current_hsk_level") or 1
    index = sub.get("current_word_index") or 0

    word = get_word_at_index(level, index)
    if not word:
        logger.warning("No word found for chat_id=%s level=%s index=%s", chat_id, level, index)
        return

    logger.info("Sending lesson to chat_id=%s word=%s", chat_id, word["hanzi"])

    # 1. Generate and send lesson content via Claude
    try:
        lesson_text = generate_lesson(word)
    except Exception as e:
        logger.error("Claude API error for chat_id=%s: %s", chat_id, e)
        # Fallback minimal lesson
        lesson_text = (
            f"📖 Chữ hôm nay: <b>{word['hanzi']}</b> ({word['pinyin']}) — HSK {word['hsk_level']}\n\n"
            f"📝 Nghĩa: {word['meaning']}"
        )

    ok = send_message(chat_id, lesson_text)
    if not ok:
        logger.error("Failed to send lesson to chat_id=%s", chat_id)
        return

    # 1b. Send pronunciation audio
    send_voice(chat_id, word)

    # 1c. Send stroke order image
    send_stroke_order(chat_id, word)

    # 2. Send quiz
    send_quiz(chat_id, word, all_words)

    # 3. Advance word index
    from hsk_words import get_words_for_level
    level_words = get_words_for_level(level)
    new_index = (index + 1) % len(level_words) if level_words else 0
    db.update_word_index(chat_id, new_index)

    # 4. Update streak
    db.update_streak(chat_id)

    logger.info("Done for chat_id=%s. Next index=%s", chat_id, new_index)


def main():
    logger.info("Starting daily lesson dispatch...")
    # Support hardcoded subscribers via env var (comma-separated chat_ids)
    # e.g. SUBSCRIBER_IDS=123456789,987654321
    env_ids = os.environ.get("SUBSCRIBER_IDS", "")
    if env_ids:
        subscribers = [{"chat_id": int(cid.strip()), "current_hsk_level": 1, "current_word_index": 0}
                       for cid in env_ids.split(",") if cid.strip()]
    else:
        subscribers = db.get_all_active_subscribers()
    logger.info("Found %d active subscribers.", len(subscribers))

    if not subscribers:
        logger.info("No active subscribers. Exiting.")
        return

    all_words = get_all_words()

    success = 0
    for sub in subscribers:
        try:
            process_subscriber(sub, all_words)
            success += 1
        except Exception as e:
            logger.error("Unhandled error for sub %s: %s", sub.get("chat_id"), e)

    logger.info("Daily lesson dispatch complete. Sent to %d/%d subscribers.", success, len(subscribers))


if __name__ == "__main__":
    main()

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
    """Send a styled character card with stroke count and color."""
    import tempfile, os as _os
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.warning("Pillow not installed; skipping character card")
        return False

    hanzi = word['hanzi']
    char = hanzi[0]
    pinyin = word.get('pinyin', '')
    meaning = word.get('meaning', '')
    hsk_level = word.get('hsk_level', 1)

    # Stroke count lookup (common HSK1-2 chars; fallback to unicode data)
    try:
        import unicodedata
        # Try to get stroke count from CJK Unified Ideographs
        stroke_count = None
        # Use a simple lookup for common chars, else estimate
        STROKE_MAP = {
            '一':1,'二':2,'三':3,'四':5,'五':4,'六':4,'七':2,'八':2,'九':2,'十':2,
            '人':2,'大':3,'小':3,'中':4,'国':8,'日':4,'月':4,'水':4,'火':4,'山':3,
            '口':3,'手':4,'心':4,'木':4,'土':3,'金':8,'女':3,'子':3,'门':3,'车':4,
            '马':3,'鸟':5,'鱼':8,'学':8,'生':5,'工':3,'天':4,'地':6,'年':6,'上':3,
            '下':3,'左':5,'右':5,'前':9,'后':6,'来':7,'去':5,'是':9,'有':6,'在':6,
            '不':4,'也':3,'都':11,'和':8,'的':8,'了':2,'我':7,'你':7,'他':5,'她':6,
            '们':5,'这':7,'那':6,'什':4,'么':3,'吗':6,'呢':8,'啊':10,'哦':9,'好':6,
            '多':6,'少':4,'大':3,'小':3,'高':10,'低':7,'长':4,'短':12,'新':13,'老':6,
            '杯':8,'子':3,'水':4,'喝':12,'吃':6,'饭':7,'菜':11,'肉':6,'鸡':7,'鱼':8,
        }
        stroke_count = STROKE_MAP.get(char)
        if stroke_count is None:
            # Rough estimate based on unicode block
            cp = ord(char)
            if 0x4E00 <= cp <= 0x9FFF:
                stroke_count = 8  # average CJK
    except Exception:
        stroke_count = None

    # Color scheme by HSK level
    LEVEL_COLORS = {
        1: ((255, 236, 153), (255, 180, 0)),    # yellow
        2: ((153, 230, 255), (0, 150, 255)),    # blue
        3: ((180, 255, 180), (0, 180, 80)),     # green
        4: ((255, 180, 180), (220, 50, 50)),    # red
        5: ((220, 180, 255), (140, 50, 220)),   # purple
        6: ((255, 200, 160), (220, 100, 0)),    # orange
    }
    bg_light, accent = LEVEL_COLORS.get(hsk_level, LEVEL_COLORS[1])

    img_size = 400
    img = Image.new("RGB", (img_size, img_size), color=bg_light)
    draw = ImageDraw.Draw(img)

    # Gradient-like background: draw accent rectangle at bottom
    draw.rectangle([0, img_size - 80, img_size, img_size], fill=accent)

    # Grid lines (calligraphy style)
    grid_color = (200, 200, 200, 128)
    mid = img_size // 2
    # Draw dashed-style grid by drawing short segments
    for i in range(0, img_size - 80, 10):
        if (i // 10) % 2 == 0:
            draw.line([(mid, i), (mid, i + 8)], fill=(210, 210, 210), width=1)
            draw.line([(i, mid - 40), (i + 8, mid - 40)], fill=(210, 210, 210), width=1)
    # Solid cross lines
    draw.line([(mid, 0), (mid, img_size - 80)], fill=(200, 200, 200), width=1)
    draw.line([(0, mid - 40), (img_size, mid - 40)], fill=(200, 200, 200), width=1)
    # Border
    draw.rectangle([2, 2, img_size - 3, img_size - 80 - 2], outline=accent, width=3)

    # Main character
    font_big = _get_cjk_font(200)
    if font_big is None:
        logger.warning("No CJK font; skipping character card")
        return False

    try:
        bbox = draw.textbbox((0, 0), char, font=font_big)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (img_size - tw) // 2 - bbox[0]
        y = (img_size - 80 - th) // 2 - bbox[1] - 10
    except AttributeError:
        tw, th = draw.textsize(char, font=font_big)
        x = (img_size - tw) // 2
        y = (img_size - 80 - th) // 2 - 10

    # Shadow
    draw.text((x + 3, y + 3), char, fill=(0, 0, 0, 60), font=font_big)
    draw.text((x, y), char, fill=(30, 30, 30), font=font_big)

    # Bottom bar text
    font_small = _get_cjk_font(22)
    if font_small:
        # Pinyin + meaning on left
        bottom_text = f"{pinyin}  |  {meaning}"
        draw.text((12, img_size - 68), bottom_text, fill=(255, 255, 255), font=font_small)
        # HSK badge on right
        hsk_text = f"HSK {hsk_level}"
        try:
            hbbox = draw.textbbox((0, 0), hsk_text, font=font_small)
            hw = hbbox[2] - hbbox[0]
        except AttributeError:
            hw, _ = draw.textsize(hsk_text, font=font_small)
        draw.text((img_size - hw - 12, img_size - 68), hsk_text, fill=(255, 255, 255), font=font_small)
        # Stroke count
        if stroke_count:
            sc_text = f"✍ {stroke_count} net"
            draw.text((12, img_size - 40), sc_text, fill=(255, 255, 255), font=font_small)

    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        tmp_path = f.name
    try:
        img.save(tmp_path, "PNG")
        url = f"{TELEGRAM_API}/sendPhoto"
        with open(tmp_path, 'rb') as img_file:
            resp = requests.post(
                url,
                data={"chat_id": chat_id, "caption": f"✍️ {char} ({pinyin}) — {meaning}"},
                files={"photo": img_file},
                timeout=30,
            )
        if not resp.ok:
            logger.warning("sendPhoto card failed for %s: %s", chat_id, resp.text)
            return False
        return True
    except Exception as e:
        logger.error("sendPhoto card exception for %s: %s", chat_id, e)
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
    try:
        db.update_word_index(chat_id, new_index)
    except Exception as e:
        logger.warning("db.update_word_index failed for %s: %s", chat_id, e)
    _write_index_update(chat_id, new_index)

    # 4. Update streak
    db.update_streak(chat_id)

    logger.info("Done for chat_id=%s. Next index=%s", chat_id, new_index)


def _gh_var_index(chat_id: int) -> int:
    """Read persisted word index from env var set by workflow (WORD_INDEX_<chat_id>)."""
    val = os.environ.get(f"WORD_INDEX_{chat_id}", "0").strip()
    try:
        return int(val)
    except ValueError:
        return 0


def _write_index_update(chat_id: int, new_index: int):
    """Append updated index to a temp file for workflow to persist."""
    import tempfile
    path = os.path.join(tempfile.gettempdir(), "word_index_updates.txt")
    with open(path, "a") as f:
        f.write(f"{chat_id}={new_index}\n")


def main():
    logger.info("Starting daily lesson dispatch...")
    # Support hardcoded subscribers via env var (comma-separated chat_ids)
    # e.g. SUBSCRIBER_IDS=123456789,987654321
    env_ids = os.environ.get("SUBSCRIBER_IDS", "")
    use_gh_vars = bool(env_ids)
    if env_ids:
        subscribers = [
            {
                "chat_id": int(cid.strip()),
                "current_hsk_level": 1,
                "current_word_index": _gh_var_index(int(cid.strip())),
            }
            for cid in env_ids.split(",") if cid.strip()
        ]
    else:
        subscribers = db.get_all_active_subscribers()
        use_gh_vars = False
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

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


def send_stroke_order(chat_id: int, word: dict) -> bool:
    """Send stroke order GIF for a Chinese character via animCJK CDN."""
    hanzi = word['hanzi']
    # For multi-character words, use only the first character
    char = hanzi[0]
    code = format(ord(char), '05x')
    gif_url = f"https://raw.githubusercontent.com/parsimonhi/animCJK/master/svgsJa/{code}.svg"

    # Try animCJK SVG first, fallback to stroke order info
    url = f"{TELEGRAM_API}/sendPhoto"
    # Use stroke order from stroke-order.info as photo URL
    photo_url = f"https://www.strokeorder.info/assets/bishun/gif/{format(ord(char), 'x').upper()}.gif"

    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": f"✍️ Thứ tự nét: {char}",
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if not resp.ok:
            logger.warning("sendPhoto stroke order failed for %s: %s", chat_id, resp.text)
            return False
        return True
    except Exception as e:
        logger.error("sendPhoto exception for %s: %s", chat_id, e)
        return False


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

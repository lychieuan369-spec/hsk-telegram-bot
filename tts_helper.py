"""
TTS helper — generate Mandarin pronunciation audio using gTTS.
Returns audio as bytes for sending via Telegram bot.
"""

import io
import logging

logger = logging.getLogger(__name__)


def get_pronunciation_audio(hanzi: str) -> bytes | None:
    """
    Generate TTS audio for a Chinese word.
    Returns audio bytes (mp3) or None if gTTS unavailable.
    """
    try:
        from gtts import gTTS
        tts = gTTS(text=hanzi, lang="zh-CN", slow=True)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except ImportError:
        logger.warning("gTTS not installed. Run: pip install gTTS")
        return None
    except Exception as e:
        logger.error(f"TTS error for '{hanzi}': {e}")
        return None

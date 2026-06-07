"""
Content generator using Claude API (claude-haiku-4-5-20251001).
Generates chiết tự lesson content and quiz options for HSK words.
"""

import os
import random
import anthropic

_client = None

def get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    return _client


def generate_lesson(word: dict) -> str:
    """Generate daily lesson content for a Chinese character using Claude."""
    prompt = f"""Bạn là chuyên gia chiết tự chữ Hán. Viết nội dung học tiếng Trung cho chữ:

Chữ Hán: {word['hanzi']}
Pinyin: {word['pinyin']}
Nghĩa: {word['meaning']}
Cấp độ: HSK {word['hsk_level']}

Viết theo format CHÍNH XÁC này (dùng emoji, ngắn gọn, hấp dẫn):

📖 Chữ hôm nay: {word['hanzi']} ({word['pinyin']}) — HSK {word['hsk_level']}

🔍 Chiết tự:
[Phân tích bộ thủ, nguồn gốc ý nghĩa từng phần, liên kết logic]

📝 Nghĩa: {word['meaning']}
🗣️ Phiên âm: {word['pinyin']}
💬 Ví dụ: [1 câu ví dụ thực tế có pinyin và nghĩa tiếng Việt]

🧠 Ghi nhớ: [1 câu mnemonic ngắn, dễ nhớ, sáng tạo bằng tiếng Việt]

⚡ Mẹo: [1 tip học nhanh hoặc liên kết với từ liên quan]"""

    msg = get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text


def generate_quiz_options(word: dict, all_words: list) -> dict:
    """
    Generate 4 multiple choice options for a word quiz.
    Returns dict with options list, correct_idx, and labels.
    """
    correct = word["meaning"]
    other_words = [w for w in all_words if w["hanzi"] != word["hanzi"]]
    wrong_words = random.sample(other_words, min(3, len(other_words)))
    options = [correct] + [w["meaning"] for w in wrong_words]
    random.shuffle(options)
    correct_idx = options.index(correct)
    return {
        "options": options,
        "correct_idx": correct_idx,
        "labels": ["A", "B", "C", "D"],
    }

"""
Content generator for HSK words.
Loads pre-generated chiết tự lesson content from hsk_content.json.
Falls back to Groq API (llama-3.3-70b-versatile) if word not found in cache.
"""

import os
import json
import re
import random
from hsk_grammar import find_grammar_by_hanzi, get_random_grammar
from openai import OpenAI

_client = None
_hsk_content = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("GROQ_API_KEY", ""), base_url="https://api.groq.com/openai/v1")
    return _client


def _load_hsk_content() -> dict:
    global _hsk_content
    if _hsk_content is None:
        json_path = os.path.join(os.path.dirname(__file__), "hsk_content.json")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                _hsk_content = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _hsk_content = {}
    return _hsk_content


def generate_lesson(word: dict) -> str:
    """Generate daily lesson content for a Chinese character.

    Loads from hsk_content.json first. Falls back to Groq API if not found.
    """
    content_map = _load_hsk_content()
    if word["hanzi"] in content_map:
        return content_map[word["hanzi"]]

    prompt = f"""Bạn là chuyên gia chiết tự chữ Hán. Viết nội dung học tiếng Trung cho chữ:

Chữ Hán: {word['hanzi']}
Pinyin: {word['pinyin']}
Nghĩa: {word['meaning']}
Cấp độ: HSK {word['hsk_level']}

Viết theo format CHÍNH XÁC này:

📖 **Chữ hôm nay: {word['hanzi']} ({word['pinyin']}) — HSK {word['hsk_level']}**
📝 Nghĩa: {word['meaning']}

---

🔍 **Chiết tự chữ phồn thể:**
[Liệt kê từng bộ thủ theo dạng bullet, mỗi bộ gồm: ký tự bộ thủ + (tên Hán Việt): nghĩa nguyên gốc → tượng trưng cho điều gì]
Ví dụ:
• 爪 (Trảo): móng vuốt → tượng trưng cho sự nắm giữ, bao bọc
• 冖 (Mịch): che đậy → bảo vệ bên trong
• 心 (Tâm): trái tim → cảm xúc, tình cảm
• 友 (Hữu): bạn bè → hành động yêu thương, gắn bó

✂️ **Chữ giản thể:** [chữ giản thể]
• Bộ thủ giữ lại: [liệt kê bộ nào còn]
• Bộ thủ lược bỏ: [liệt kê bộ nào mất, lý do nếu biết]

💡 **Câu chuyện chiết tự:**
[1-2 câu kết nối tất cả bộ thủ thành narrative có nghĩa, giải thích TẠI SAO chữ này mang nghĩa đó. Dùng bold cho tên bộ thủ.]

🗣️ **Hướng dẫn đọc:**
• Thanh điệu: thanh [số] — [tên thanh: bằng/sắc/hỏi/nặng] — [mô tả đường nét: ngang/lên/xuống-lên/xuống thẳng]
• Cách đọc: [giải thích phát âm initial + final cụ thể, ví dụ: "zh" đọc như "tr" tiếng Việt nhưng lưỡi cuộn]
• Bẫy phát âm: [người Việt hay sai chỗ nào — ví dụ nhầm x/sh, q/ch, lẫn lộn thanh 2-3]
• Gần giống tiếng Việt: [âm nào trong tiếng Việt gần nhất để liên tưởng — ví dụ: "ài" ≈ "ái" trong "yêu ái"]

💬 **Ví dụ thực tế:**
[câu ví dụ tiếng Trung] ([pinyin])
→ [nghĩa tiếng Việt]

🧠 **Mnemonic:**
[1 câu ghi nhớ ngắn, sáng tạo, dễ thuộc bằng tiếng Việt — liên kết hình ảnh bộ thủ]"""

    response = get_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    content = response.choices[0].message.content
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    content = content.replace('**', '')
    return content


def generate_grammar_section(word: dict) -> str:
    """
    Return grammar section string for a word.
    HSK 1-3: use static hsk_grammar.py data.
    HSK 4-6: generate dynamically via Groq.
    """
    level = word.get("hsk_level", 1)
    hanzi = word["hanzi"]

    if level <= 3:
        point = find_grammar_by_hanzi(hanzi, level)
        if not point:
            point = get_random_grammar(level)
        if point:
            return (
                f"\n\n📐 <b>Ngữ pháp liên quan:</b>\n"
                f"• Pattern: <code>{point['pattern']}</code>\n"
                f"• {point['explanation']}\n"
                f"• Ví dụ: {point['example_cn']}\n"
                f"  → {point['example_vn']}"
            )
        return ""
    else:
        # Premium: Groq generates grammar dynamically
        try:
            prompt = (
                f"Chữ Hán: {hanzi} ({word.get('pinyin','')}) — HSK {level}\n"
                f"Nghĩa: {word.get('meaning','')}\n\n"
                "Viết 1 grammar point ngắn liên quan đến chữ này (tiếng Việt), gồm:\n"
                "- Pattern (công thức ngữ pháp)\n"
                "- Giải thích 1 câu\n"
                "- 1 câu ví dụ tiếng Trung + nghĩa tiếng Việt\n"
                "Giữ ngắn gọn, tối đa 4 dòng."
            )
            resp = get_client().chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            grammar_text = resp.choices[0].message.content.strip()
            return f"\n\n📐 <b>Ngữ pháp:</b>\n{grammar_text}"
        except Exception:
            return ""


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

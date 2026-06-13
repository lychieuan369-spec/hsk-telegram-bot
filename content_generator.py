"""
Content generator using Groq API (llama-3.1-8b-instant).
Generates chiết tự lesson content and quiz options for HSK words.
"""

import os
import random
from openai import OpenAI

_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("GROQ_API_KEY", ""), base_url="https://api.groq.com/openai/v1")
    return _client


def generate_lesson(word: dict) -> str:
    """Generate daily lesson content for a Chinese character using Groq."""
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
    return response.choices[0].message.content


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

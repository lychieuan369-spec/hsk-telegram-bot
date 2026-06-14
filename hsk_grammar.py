"""
HSK Grammar points HSK 1-3 (free tier).
HSK 4-6 grammar generated dynamically via Groq API.
Each entry: pattern, explanation, example_cn, example_vn, related_words
"""

HSK_GRAMMAR = {
    1: [
        {
            "id": "hsk1_g01",
            "pattern": "主 + 是 + 宾 (S + 是 + O)",
            "explanation": "Câu phán đoán: dùng 是 nối chủ ngữ và tân ngữ (= 'là')",
            "example_cn": "我是老师。",
            "example_vn": "Tôi là giáo viên.",
            "related_words": ["是", "我", "你", "他", "她"],
        },
        {
            "id": "hsk1_g02",
            "pattern": "主 + 有 + 宾 (S + 有 + O)",
            "explanation": "有 biểu đạt sở hữu hoặc tồn tại (= 'có')",
            "example_cn": "我有一个朋友。",
            "example_vn": "Tôi có một người bạn.",
            "related_words": ["有", "没有"],
        },
        {
            "id": "hsk1_g03",
            "pattern": "不 + 动词 (不 + V)",
            "explanation": "不 phủ định động từ ở hiện tại/tương lai (= 'không')",
            "example_cn": "我不吃米饭。",
            "example_vn": "Tôi không ăn cơm.",
            "related_words": ["不", "吃", "喝", "去", "来"],
        },
        {
            "id": "hsk1_g04",
            "pattern": "很 + 形容词 (很 + Adj)",
            "explanation": "很 thường đứng trước tính từ trong câu đơn (= 'rất')",
            "example_cn": "她很漂亮。",
            "example_vn": "Cô ấy rất xinh đẹp.",
            "related_words": ["很", "好", "大", "小", "漂亮", "高兴"],
        },
        {
            "id": "hsk1_g05",
            "pattern": "……吗？ (câu hỏi Yes/No)",
            "explanation": "Thêm 吗 cuối câu để hỏi Yes/No",
            "example_cn": "你是学生吗？",
            "example_vn": "Bạn có phải là học sinh không?",
            "related_words": ["吗"],
        },
        {
            "id": "hsk1_g06",
            "pattern": "也 + 动词/形容词",
            "explanation": "也 = 'cũng', đứng trước động từ hoặc tính từ",
            "example_cn": "我也喜欢喝茶。",
            "example_vn": "Tôi cũng thích uống trà.",
            "related_words": ["也"],
        },
        {
            "id": "hsk1_g07",
            "pattern": "都 + 动词 (都 + V)",
            "explanation": "都 = 'đều/tất cả', đứng trước động từ, chỉ toàn bộ",
            "example_cn": "他们都是学生。",
            "example_vn": "Họ đều là học sinh.",
            "related_words": ["都"],
        },
        {
            "id": "hsk1_g08",
            "pattern": "几 + 量词 + 名词 (hỏi số lượng nhỏ)",
            "explanation": "几 hỏi số lượng dưới 10, cần lượng từ",
            "example_cn": "你有几个朋友？",
            "example_vn": "Bạn có mấy người bạn?",
            "related_words": ["几", "个"],
        },
    ],
    2: [
        {
            "id": "hsk2_g01",
            "pattern": "在 + 地点 + 动词 (在 + Place + V)",
            "explanation": "在 chỉ địa điểm hành động diễn ra (= 'ở/tại')",
            "example_cn": "我在家吃饭。",
            "example_vn": "Tôi ăn cơm ở nhà.",
            "related_words": ["在", "家", "学校", "公司"],
        },
        {
            "id": "hsk2_g02",
            "pattern": "动词 + 了 (V + 了, hoàn thành)",
            "explanation": "了 sau động từ chỉ hành động đã hoàn thành",
            "example_cn": "我吃了饭。",
            "example_vn": "Tôi đã ăn cơm rồi.",
            "related_words": ["了"],
        },
        {
            "id": "hsk2_g03",
            "pattern": "正在 + 动词 (đang làm gì)",
            "explanation": "正在 chỉ hành động đang diễn ra ngay lúc nói",
            "example_cn": "他正在看书。",
            "example_vn": "Anh ấy đang đọc sách.",
            "related_words": ["正在", "在", "呢"],
        },
        {
            "id": "hsk2_g04",
            "pattern": "想 + 动词 (muốn làm gì)",
            "explanation": "想 = 'muốn', biểu đạt ý muốn hoặc suy nghĩ",
            "example_cn": "我想去北京。",
            "example_vn": "Tôi muốn đến Bắc Kinh.",
            "related_words": ["想", "要", "会"],
        },
        {
            "id": "hsk2_g05",
            "pattern": "比 + A + 比 + B + 形容词 (so sánh hơn)",
            "explanation": "A 比 B + adj = A [tính từ] hơn B",
            "example_cn": "今天比昨天冷。",
            "example_vn": "Hôm nay lạnh hơn hôm qua.",
            "related_words": ["比"],
        },
        {
            "id": "hsk2_g06",
            "pattern": "从……到…… (từ... đến...)",
            "explanation": "从...到... chỉ phạm vi thời gian hoặc không gian",
            "example_cn": "从北京到上海要两个小时。",
            "example_vn": "Từ Bắc Kinh đến Thượng Hải mất hai tiếng.",
            "related_words": ["从", "到"],
        },
        {
            "id": "hsk2_g07",
            "pattern": "因为……所以…… (vì... nên...)",
            "explanation": "Cặp liên từ nhân quả: vì...nên...",
            "example_cn": "因为下雨，所以我不去了。",
            "example_vn": "Vì trời mưa nên tôi không đi nữa.",
            "related_words": ["因为", "所以"],
        },
        {
            "id": "hsk2_g08",
            "pattern": "动词 + 过 (từng đã làm)",
            "explanation": "过 sau động từ chỉ kinh nghiệm đã từng có",
            "example_cn": "我去过中国。",
            "example_vn": "Tôi đã từng đến Trung Quốc.",
            "related_words": ["过"],
        },
    ],
    3: [
        {
            "id": "hsk3_g01",
            "pattern": "把 + O + V + 补 (câu 把)",
            "explanation": "把 mang tân ngữ lên trước động từ, nhấn mạnh xử lý đối tượng",
            "example_cn": "请把书放在桌上。",
            "example_vn": "Hãy đặt sách lên bàn.",
            "related_words": ["把"],
        },
        {
            "id": "hsk3_g02",
            "pattern": "被 + agent + V (câu bị động)",
            "explanation": "被 = 'bị/được', chỉ chủ ngữ là đối tượng chịu tác động",
            "example_cn": "我的手机被他拿走了。",
            "example_vn": "Điện thoại của tôi bị anh ấy lấy đi rồi.",
            "related_words": ["被"],
        },
        {
            "id": "hsk3_g03",
            "pattern": "虽然……但是…… (tuy... nhưng...)",
            "explanation": "Cặp liên từ nhượng bộ: tuy... nhưng...",
            "example_cn": "虽然很累，但是我还要学习。",
            "example_vn": "Tuy rất mệt nhưng tôi vẫn phải học.",
            "related_words": ["虽然", "但是"],
        },
        {
            "id": "hsk3_g04",
            "pattern": "如果……就…… (nếu... thì...)",
            "explanation": "Câu điều kiện: nếu...thì...",
            "example_cn": "如果你来，我就很高兴。",
            "example_vn": "Nếu bạn đến thì tôi rất vui.",
            "related_words": ["如果", "就"],
        },
        {
            "id": "hsk3_g05",
            "pattern": "动词 + 得 + 补语 (kết quả/mức độ)",
            "explanation": "得 nối động từ với bổ ngữ chỉ kết quả hoặc mức độ",
            "example_cn": "他说得很好。",
            "example_vn": "Anh ấy nói rất tốt.",
            "related_words": ["得"],
        },
        {
            "id": "hsk3_g06",
            "pattern": "越来越 + 形容词 (ngày càng...)",
            "explanation": "越来越 = ngày càng, chỉ xu hướng tăng dần",
            "example_cn": "天气越来越冷了。",
            "example_vn": "Thời tiết ngày càng lạnh hơn.",
            "related_words": ["越来越"],
        },
        {
            "id": "hsk3_g07",
            "pattern": "对……来说 (đối với...)",
            "explanation": "đối với [ai/cái gì] mà nói",
            "example_cn": "对我来说，汉语很有趣。",
            "example_vn": "Đối với tôi, tiếng Trung rất thú vị.",
            "related_words": ["对", "来说"],
        },
        {
            "id": "hsk3_g08",
            "pattern": "除了……以外，还/都 (ngoài... còn/đều)",
            "explanation": "Ngoài A ra còn có B (还) hoặc tất cả trừ A (都)",
            "example_cn": "除了中文，他还会英文。",
            "example_vn": "Ngoài tiếng Trung anh ấy còn biết tiếng Anh.",
            "related_words": ["除了", "以外", "还"],
        },
    ],
}


def get_grammar_for_level(level: int) -> list:
    """Return grammar points for given HSK level (1-3 only, 4-6 use Groq)."""
    return HSK_GRAMMAR.get(level, [])


def find_grammar_by_hanzi(hanzi: str, level: int) -> dict | None:
    """Find a grammar point related to a specific hanzi at given level."""
    points = get_grammar_for_level(level)
    for point in points:
        if hanzi in point.get("related_words", []):
            return point
    return None


def get_random_grammar(level: int) -> dict | None:
    """Return a random grammar point for given level."""
    import random
    points = get_grammar_for_level(level)
    return random.choice(points) if points else None

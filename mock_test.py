"""
Mock HSK test — 20 questions drawn from user's current HSK level words.
Uses the same quiz format as the main bot but tracks test score separately.
"""

import random
from hsk_words import get_words_for_level, get_all_words
from content_generator import generate_quiz_options


def generate_mock_test(hsk_level: int, num_questions: int = 20) -> list[dict]:
    """
    Generate a mock test for the given HSK level.
    Returns list of question dicts, each with:
      - word: dict (hanzi, pinyin, meaning, hsk_level)
      - options: list[str] — 4 answer choices
      - correct_idx: int
      - labels: list[str] — ["A","B","C","D"]
    """
    level_words = get_words_for_level(hsk_level)
    all_words = get_all_words()

    if len(level_words) < 4:
        return []

    sample_size = min(num_questions, len(level_words))
    selected = random.sample(level_words, sample_size)

    questions = []
    for word in selected:
        quiz_data = generate_quiz_options(word, all_words)
        questions.append({
            "word": word,
            "options": quiz_data["options"],
            "correct_idx": quiz_data["correct_idx"],
            "labels": quiz_data["labels"],
        })

    return questions


def score_test(answers: list[bool]) -> dict:
    """
    Calculate test results.
    answers: list of bool (True=correct, False=wrong)
    Returns dict with total, correct, score_pct, passed (>=60%)
    """
    total = len(answers)
    correct = sum(answers)
    score_pct = round(correct / total * 100) if total > 0 else 0
    return {
        "total": total,
        "correct": correct,
        "score_pct": score_pct,
        "passed": score_pct >= 60,
    }

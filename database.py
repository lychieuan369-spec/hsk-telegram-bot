"""
Database module supporting both SQLite (local/Railway) and PostgreSQL (Supabase/prod).
If DATABASE_URL env var starts with 'postgresql', uses psycopg2; otherwise SQLite.
"""

import os
import sqlite3
import json
from datetime import date, timedelta
from typing import Optional

DATABASE_URL = os.environ.get("DATABASE_URL", "")
DATABASE_PATH = os.environ.get("DATABASE_PATH", "hsk_bot.db")

USE_POSTGRES = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")


def _get_conn():
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def _placeholder():
    """Return the correct placeholder for the current DB driver."""
    return "%s" if USE_POSTGRES else "?"


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    cur = conn.cursor()

    if USE_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                chat_id BIGINT PRIMARY KEY,
                username TEXT,
                active BOOLEAN DEFAULT TRUE,
                plan TEXT DEFAULT 'basic',
                joined_at DATE DEFAULT CURRENT_DATE,
                current_hsk_level INTEGER DEFAULT 1,
                current_word_index INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS quiz_history (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                word TEXT,
                correct BOOLEAN,
                next_review DATE,
                review_count INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS streak (
                chat_id BIGINT PRIMARY KEY,
                streak_days INTEGER DEFAULT 0,
                last_activity DATE
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                chat_id INTEGER PRIMARY KEY,
                username TEXT,
                active INTEGER DEFAULT 1,
                plan TEXT DEFAULT 'basic',
                joined_at TEXT DEFAULT (date('now')),
                current_hsk_level INTEGER DEFAULT 1,
                current_word_index INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS quiz_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                word TEXT,
                correct INTEGER,
                next_review TEXT,
                review_count INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS streak (
                chat_id INTEGER PRIMARY KEY,
                streak_days INTEGER DEFAULT 0,
                last_activity TEXT
            )
        """)

    conn.commit()
    cur.close()
    conn.close()


def _row_to_dict(row, cur=None):
    if row is None:
        return None
    if USE_POSTGRES:
        if cur is not None:
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row))
        return dict(row)
    else:
        return dict(row)


def add_subscriber(chat_id: int, username: str):
    p = _placeholder()
    conn = _get_conn()
    cur = conn.cursor()
    if USE_POSTGRES:
        cur.execute(f"""
            INSERT INTO subscribers (chat_id, username, active, plan, joined_at, current_hsk_level, current_word_index)
            VALUES ({p}, {p}, TRUE, 'basic', CURRENT_DATE, 1, 0)
            ON CONFLICT (chat_id) DO UPDATE SET active = TRUE, username = EXCLUDED.username
        """, (chat_id, username or ""))
    else:
        cur.execute(f"""
            INSERT OR REPLACE INTO subscribers (chat_id, username, active, plan, joined_at, current_hsk_level, current_word_index)
            VALUES ({p}, {p}, 1, 'basic', date('now'), 1, 0)
        """, (chat_id, username or ""))
    conn.commit()
    cur.close()
    conn.close()


def remove_subscriber(chat_id: int):
    p = _placeholder()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE subscribers SET active = {'FALSE' if USE_POSTGRES else '0'} WHERE chat_id = {p}", (chat_id,))
    conn.commit()
    cur.close()
    conn.close()


def get_all_active_subscribers() -> list:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM subscribers WHERE active = TRUE" if USE_POSTGRES else "SELECT * FROM subscribers WHERE active = 1")
    rows = cur.fetchall()
    result = [_row_to_dict(r, cur) for r in rows]
    cur.close()
    conn.close()
    return result


def get_subscriber(chat_id: int) -> Optional[dict]:
    p = _placeholder()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM subscribers WHERE chat_id = {p}", (chat_id,))
    row = cur.fetchone()
    result = _row_to_dict(row, cur)
    cur.close()
    conn.close()
    return result


def update_word_index(chat_id: int, index: int):
    p = _placeholder()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE subscribers SET current_word_index = {p} WHERE chat_id = {p}", (index, chat_id))
    conn.commit()
    cur.close()
    conn.close()


def update_hsk_level(chat_id: int, level: int):
    p = _placeholder()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE subscribers SET current_hsk_level = {p}, current_word_index = 0 WHERE chat_id = {p}", (level, chat_id))
    conn.commit()
    cur.close()
    conn.close()


def record_quiz(chat_id: int, word: str, correct: bool):
    """
    Update spaced repetition schedule:
    - Wrong: next review = tomorrow
    - Right 1st time: next review = 3 days
    - Right 2nd+ time: next review = 7 days
    """
    p = _placeholder()
    today = date.today()
    conn = _get_conn()
    cur = conn.cursor()

    # Check existing record
    cur.execute(f"SELECT review_count, correct FROM quiz_history WHERE chat_id = {p} AND word = {p} ORDER BY id DESC LIMIT 1", (chat_id, word))
    existing = cur.fetchone()

    if correct:
        prev_count = 0
        if existing:
            prev_correct = existing[1]
            prev_count = existing[0] if existing[0] else 0
            if USE_POSTGRES and isinstance(prev_correct, bool):
                prev_was_correct = prev_correct
            else:
                prev_was_correct = bool(prev_correct)
        else:
            prev_was_correct = False

        if not existing or not prev_was_correct:
            next_review = today + timedelta(days=3)
            review_count = 1
        else:
            next_review = today + timedelta(days=7)
            review_count = (prev_count or 0) + 1
    else:
        next_review = today + timedelta(days=1)
        review_count = 0

    next_review_str = next_review.isoformat()
    correct_val = correct if USE_POSTGRES else (1 if correct else 0)

    cur.execute(f"""
        INSERT INTO quiz_history (chat_id, word, correct, next_review, review_count)
        VALUES ({p}, {p}, {p}, {p}, {p})
    """, (chat_id, word, correct_val, next_review_str, review_count))

    conn.commit()
    cur.close()
    conn.close()


def get_words_to_review(chat_id: int) -> list:
    """Return words where next_review <= today."""
    p = _placeholder()
    today = date.today().isoformat()
    conn = _get_conn()
    cur = conn.cursor()

    # Get distinct words due for review (most recent record per word)
    if USE_POSTGRES:
        cur.execute(f"""
            SELECT DISTINCT ON (word) word, next_review, review_count
            FROM quiz_history
            WHERE chat_id = {p}
            ORDER BY word, id DESC
        """, (chat_id,))
    else:
        cur.execute(f"""
            SELECT word, next_review, review_count
            FROM quiz_history
            WHERE chat_id = {p}
            GROUP BY word
            HAVING id = MAX(id)
        """, (chat_id,))

    rows = cur.fetchall()
    result = []
    for row in rows:
        if USE_POSTGRES:
            word_data = _row_to_dict(row, cur)
        else:
            word_data = dict(row)
        nr = word_data.get("next_review")
        if nr and str(nr) <= today:
            result.append(word_data["word"])

    cur.close()
    conn.close()
    return result


def get_quiz_stats(chat_id: int) -> dict:
    """Return total quizzes and correct count."""
    p = _placeholder()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) as total, SUM(CASE WHEN correct {'IS TRUE' if USE_POSTGRES else '= 1'} THEN 1 ELSE 0 END) as correct_count FROM quiz_history WHERE chat_id = {p}", (chat_id,))
    row = cur.fetchone()
    if USE_POSTGRES:
        d = _row_to_dict(row, cur)
    else:
        d = dict(row)
    cur.close()
    conn.close()
    total = d.get("total") or 0
    correct_count = d.get("correct_count") or 0
    return {"total": total, "correct": correct_count}


def update_streak(chat_id: int):
    p = _placeholder()
    today = date.today()
    today_str = today.isoformat()
    yesterday_str = (today - timedelta(days=1)).isoformat()
    conn = _get_conn()
    cur = conn.cursor()

    cur.execute(f"SELECT streak_days, last_activity FROM streak WHERE chat_id = {p}", (chat_id,))
    row = cur.fetchone()

    if row is None:
        if USE_POSTGRES:
            cur.execute(f"INSERT INTO streak (chat_id, streak_days, last_activity) VALUES ({p}, 1, {p})", (chat_id, today_str))
        else:
            cur.execute(f"INSERT INTO streak (chat_id, streak_days, last_activity) VALUES ({p}, 1, {p})", (chat_id, today_str))
    else:
        if USE_POSTGRES:
            d = _row_to_dict(row, cur)
        else:
            d = dict(row)
        last_activity = str(d.get("last_activity") or "")
        streak_days = d.get("streak_days") or 0

        if last_activity == today_str:
            # Already updated today
            cur.close()
            conn.close()
            return
        elif last_activity == yesterday_str:
            new_streak = streak_days + 1
        else:
            new_streak = 1

        cur.execute(f"UPDATE streak SET streak_days = {p}, last_activity = {p} WHERE chat_id = {p}", (new_streak, today_str, chat_id))

    conn.commit()
    cur.close()
    conn.close()


def get_streak(chat_id: int) -> int:
    p = _placeholder()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT streak_days FROM streak WHERE chat_id = {p}", (chat_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row is None:
        return 0
    return row[0] or 0


def set_user_plan(chat_id: int, plan: str):
    """Set user plan: 'basic' or 'premium'"""
    p = _placeholder()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE subscribers SET plan = {p} WHERE chat_id = {p}", (plan, chat_id))
    conn.commit()
    cur.close()
    conn.close()


def get_user_plan(chat_id: int) -> str:
    """Return 'basic' or 'premium'. Default 'basic'."""
    p = _placeholder()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT plan FROM subscribers WHERE chat_id = {p}", (chat_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row is None:
        return "basic"
    return row[0] or "basic"


def get_all_premium_subscribers() -> list:
    """Return all active premium subscribers."""
    conn = _get_conn()
    cur = conn.cursor()
    active_val = "TRUE" if USE_POSTGRES else "1"
    cur.execute(f"SELECT * FROM subscribers WHERE active = {active_val} AND plan = 'premium'")
    rows = cur.fetchall()
    result = [_row_to_dict(r, cur) for r in rows]
    cur.close()
    conn.close()
    return result


# Initialize DB on import
init_db()

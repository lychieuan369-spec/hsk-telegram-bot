"""
HSK Telegram Bot — persistent process handling all user commands.
Uses python-telegram-bot v20 (async).
"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

import database as db
from hsk_words import get_word_at_index, get_all_words, find_word_by_hanzi, get_words_for_level
from content_generator import generate_lesson, generate_quiz_options

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]


# ──────────────────────────────────────────────
# Command Handlers
# ──────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register subscriber and send welcome message."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    db.add_subscriber(chat_id, user.username or user.first_name or "")
    sub = db.get_subscriber(chat_id)
    level = sub["current_hsk_level"] if sub else 1

    welcome_text = (
        f"🎉 Chào mừng {user.first_name} đến với HSK Daily Bot!\n\n"
        f"📚 Bạn đang học: HSK {level}\n\n"
        "Mỗi ngày lúc 7h sáng, bot sẽ gửi 1 chữ Hán mới kèm chiết tự & quiz.\n\n"
        "📋 Các lệnh:\n"
        "/progress — Xem tiến độ học\n"
        "/review — Ôn tập từ đã học\n"
        "/quiz — Quiz từ hôm nay\n"
        "/setlevel 1 đến 6 — Đổi cấp độ HSK\n"
        "/stop — Dừng nhận bài học\n\n"
        "Chúc bạn học tốt! 加油 🔥"
    )
    await update.message.reply_text(welcome_text)


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unsubscribe user."""
    chat_id = update.effective_chat.id
    db.remove_subscriber(chat_id)
    await update.message.reply_text(
        "😢 Bạn đã dừng nhận bài học.\n"
        "Nhắn /start bất cứ lúc nào để học lại nhé!"
    )


async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show learning progress."""
    chat_id = update.effective_chat.id
    sub = db.get_subscriber(chat_id)

    if not sub:
        await update.message.reply_text("Bạn chưa đăng ký. Nhắn /start để bắt đầu!")
        return

    level = sub["current_hsk_level"]
    word_index = sub["current_word_index"]
    streak = db.get_streak(chat_id)
    stats = db.get_quiz_stats(chat_id)

    total = stats["total"]
    correct = stats["correct"]
    accuracy = round(correct / total * 100) if total > 0 else 0

    level_words = get_words_for_level(level)
    total_in_level = len(level_words)

    text = (
        f"📊 Tiến độ học của bạn\n\n"
        f"🎯 Cấp độ hiện tại: HSK {level}\n"
        f"📖 Đã học: {word_index}/{total_in_level} từ (HSK {level})\n"
        f"🔥 Streak: {streak} ngày liên tiếp\n"
        f"✅ Độ chính xác quiz: {accuracy}% ({correct}/{total})\n\n"
        f"Tiếp tục cố gắng nhé! 💪"
    )
    await update.message.reply_text(text)


async def review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send up to 5 words due for review as quizzes."""
    chat_id = update.effective_chat.id
    sub = db.get_subscriber(chat_id)

    if not sub:
        await update.message.reply_text("Bạn chưa đăng ký. Nhắn /start để bắt đầu!")
        return

    due_words = db.get_words_to_review(chat_id)
    if not due_words:
        await update.message.reply_text(
            "🎉 Không có từ nào cần ôn tập hôm nay!\n"
            "Bạn đang học rất tốt. Hãy nhắn /quiz để học từ mới!"
        )
        return

    all_words = get_all_words()
    words_to_review = due_words[:5]

    await update.message.reply_text(
        f"📚 Ôn tập {len(words_to_review)} từ hôm nay:\n"
    )

    for hanzi in words_to_review:
        word = find_word_by_hanzi(hanzi)
        if not word:
            continue
        await _send_quiz(update.message, chat_id, word, all_words)


async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send quiz for today's word."""
    chat_id = update.effective_chat.id
    sub = db.get_subscriber(chat_id)

    if not sub:
        await update.message.reply_text("Bạn chưa đăng ký. Nhắn /start để bắt đầu!")
        return

    level = sub["current_hsk_level"]
    index = sub["current_word_index"]
    word = get_word_at_index(level, index)

    if not word:
        await update.message.reply_text("Không tìm thấy từ. Hãy thử /setlevel để đặt lại cấp độ.")
        return

    all_words = get_all_words()
    await _send_quiz(update.message, chat_id, word, all_words)


async def setlevel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change user's HSK level."""
    chat_id = update.effective_chat.id

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Dùng: /setlevel 1 đến 6\nVí dụ: /setlevel 3")
        return

    level = int(context.args[0])
    if level < 1 or level > 6:
        await update.message.reply_text("Cấp độ hợp lệ từ 1 đến 6.")
        return

    db.update_hsk_level(chat_id, level)
    await update.message.reply_text(
        f"✅ Đã chuyển sang HSK {level}!\n"
        f"Bạn sẽ học từ đầu danh sách HSK {level}.\n"
        "Nhắn /quiz để bắt đầu ngay!"
    )


# ──────────────────────────────────────────────
# Quiz Helper
# ──────────────────────────────────────────────

async def _send_quiz(message, chat_id: int, word: dict, all_words: list):
    """Send a quiz inline keyboard for a given word."""
    quiz_data = generate_quiz_options(word, all_words)
    options = quiz_data["options"]
    correct_idx = quiz_data["correct_idx"]
    labels = quiz_data["labels"]

    keyboard = [
        [
            InlineKeyboardButton(
                f"{labels[0]}: {_truncate(options[0])}",
                callback_data=f"quiz_{word['hanzi']}_{correct_idx}_0",
            ),
            InlineKeyboardButton(
                f"{labels[1]}: {_truncate(options[1])}",
                callback_data=f"quiz_{word['hanzi']}_{correct_idx}_1",
            ),
        ],
        [
            InlineKeyboardButton(
                f"{labels[2]}: {_truncate(options[2])}",
                callback_data=f"quiz_{word['hanzi']}_{correct_idx}_2",
            ),
            InlineKeyboardButton(
                f"{labels[3]}: {_truncate(options[3])}",
                callback_data=f"quiz_{word['hanzi']}_{correct_idx}_3",
            ),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    quiz_text = (
        f"❓ Quiz: Chữ *{word['hanzi']}* ({word['pinyin']}) — HSK {word['hsk_level']}\n"
        f"Nghĩa là gì?"
    )
    await message.reply_text(quiz_text, reply_markup=reply_markup, parse_mode="Markdown")


def _truncate(text: str, max_len: int = 20) -> str:
    """Truncate option text for button display."""
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


# ──────────────────────────────────────────────
# Callback Query Handler (quiz answers)
# ──────────────────────────────────────────────

async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quiz answer button press."""
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    data = query.data  # format: quiz_{hanzi}_{correct_idx}_{chosen_idx}

    if not data.startswith("quiz_"):
        return

    parts = data.split("_", 3)
    if len(parts) != 4:
        return

    _, hanzi_raw, correct_idx_str, chosen_idx_str = parts
    # hanzi may contain underscores in theory, but split with maxsplit=3 handles it
    hanzi = hanzi_raw
    correct_idx = int(correct_idx_str)
    chosen_idx = int(chosen_idx_str)
    is_correct = correct_idx == chosen_idx

    # Record result
    db.record_quiz(chat_id, hanzi, is_correct)
    db.update_streak(chat_id)

    word = find_word_by_hanzi(hanzi)
    streak = db.get_streak(chat_id)
    labels = ["A", "B", "C", "D"]

    if is_correct:
        response = (
            f"✅ Đúng rồi! *{hanzi}* = {word['meaning'] if word else '?'}\n"
            f"🔥 Streak: {streak} ngày"
        )
    else:
        correct_label = labels[correct_idx]
        correct_meaning = word["meaning"] if word else "?"
        response = (
            f"❌ Sai rồi. Đáp án đúng: *{correct_label}. {correct_meaning}*\n"
            f"Sẽ ôn lại ngày mai 📅"
        )

    await query.edit_message_text(
        text=f"{query.message.text}\n\n{response}",
        parse_mode="Markdown",
    )


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("progress", progress))
    app.add_handler(CommandHandler("review", review))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("setlevel", setlevel))
    app.add_handler(CallbackQueryHandler(handle_quiz_answer, pattern=r"^quiz_"))

    logger.info("Bot started. Polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

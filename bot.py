"""
HSK Telegram Bot — persistent process handling all user commands.
Uses python-telegram-bot v20 (async).
"""

import os
import threading
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
from tts_helper import get_pronunciation_audio
from mock_test import generate_mock_test, score_test

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))


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

    plan = db.get_user_plan(chat_id)
    days_left = db.get_trial_days_remaining(chat_id)

    if plan == "premium":
        plan_badge = "💎 Premium"
        trial_line = ""
    elif days_left >= 0:
        plan_badge = f"🆓 Dùng thử ({days_left} ngày còn lại)"
        trial_line = f"\n⚠️ Học thử miễn phí còn <b>{days_left} ngày</b>. /premium để tiếp tục sau đó.\n"
    else:
        plan_badge = "⏰ Hết hạn dùng thử"
        trial_line = "\n⛔ Kỳ học thử đã kết thúc. Nhắn /premium để tiếp tục học!\n"

    welcome_text = (
        f"🎉 Chào mừng {user.first_name} đến với HSK Daily Bot!\n\n"
        f"📚 Cấp độ: HSK {level} | Gói: {plan_badge}\n"
        f"{trial_line}\n"
        "Mỗi ngày lúc 7h sáng, bot sẽ gửi 1 chữ Hán mới kèm chiết tự & quiz.\n\n"
        "📋 Các lệnh:\n"
        "/progress — Xem tiến độ học\n"
        "/review — Ôn tập từ đã học\n"
        "/quiz — Quiz từ hôm nay\n"
        "/setlevel 1-9 — Đổi cấp độ HSK\n"
        "/premium — Nâng cấp Premium (HSK 2-9, 89k/tháng)\n"
        "/say [chữ] — Nghe phát âm TTS 🔊 (Premium)\n"
        "/mocktest — Mock test HSK 10 câu (Premium)\n"
        "/stop — Dừng nhận bài học\n\n"
        "Chúc bạn học tốt! 加油 🔥\n"
        "v2.0 — HSK 1-9"
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

    days_left = db.get_trial_days_remaining(chat_id)
    if days_left == 999:
        trial_line = "💎 Gói: Premium\n"
    elif days_left >= 0:
        trial_line = f"⏳ Dùng thử: còn {days_left} ngày\n"
    else:
        trial_line = "⛔ Hết hạn dùng thử — /premium để tiếp tục\n"

    text = (
        f"📊 Tiến độ học của bạn\n\n"
        f"🎯 Cấp độ hiện tại: HSK {level}\n"
        f"📖 Đã học: {word_index}/{total_in_level} từ (HSK {level})\n"
        f"🔥 Streak: {streak} ngày liên tiếp\n"
        f"✅ Độ chính xác quiz: {accuracy}% ({correct}/{total})\n"
        f"{trial_line}\n"
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
        await update.message.reply_text("Dùng: /setlevel 1 đến 9\nVí dụ: /setlevel 3")
        return

    level = int(context.args[0])
    if level < 1 or level > 9:
        await update.message.reply_text("Cấp độ hợp lệ từ 1 đến 9.")
        return

    plan = db.get_user_plan(chat_id)
    if level >= 2 and plan != "premium":
        await update.message.reply_text(
            "🔒 HSK 2-9 dành cho thành viên Premium.\n\n"
            "💎 Nâng cấp Premium để:\n"
            "• Học HSK 2, 3, 4, 5, 6, 7, 8, 9\n"
            "• 5000+ từ vựng đầy đủ\n"
            "• Spaced repetition thông minh\n"
            "• Phát âm TTS\n\n"
            "📩 Nhắn /premium để xem chi tiết và đăng ký!"
        )
        return

    db.update_hsk_level(chat_id, level)
    await update.message.reply_text(
        f"✅ Đã chuyển sang HSK {level}!\n"
        f"Bạn sẽ học từ đầu danh sách HSK {level}.\n"
        "Nhắn /quiz để bắt đầu ngay!"
    )


async def premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show premium info and payment instructions."""
    chat_id = update.effective_chat.id
    plan = db.get_user_plan(chat_id)

    if plan == "premium":
        await update.message.reply_text(
            "💎 Bạn đang là thành viên Premium!\n\n"
            "✅ HSK 1-9 đã được mở khoá\n"
            "✅ Từ vựng nâng cao 500+ chữ\n"
            "✅ Ôn tập không giới hạn\n\n"
            "Cảm ơn bạn đã ủng hộ! 🙏"
        )
        return

    await update.message.reply_text(
        "💎 <b>Nâng cấp Premium — HSK Bot</b>\n\n"
        "🆓 <b>Gói Free (miễn phí):</b>\n"
        "• HSK 1: 150 từ cơ bản\n"
        "• Quiz hàng ngày\n"
        "• Streak tracking\n\n"
        "👑 <b>Gói Premium — 89.000đ/tháng:</b>\n"
        "• HSK 1-9 đầy đủ (5000+ từ)\n"
        "• Phát âm TTS mỗi từ\n"
        "• Spaced Repetition thông minh\n"
        "• Mock test chuẩn HSK\n"
        "• Progress analytics chi tiết\n\n"
        "💳 <b>Thanh toán:</b>\n"
        "Chuyển khoản 89.000đ\n"
        "MB Bank: 5100150678999\n"
        "Nội dung: <code>HSK [username Telegram của bạn]</code>\n\n"
        "Sau khi chuyển khoản → nhắn /confirm + ảnh bill\n\n"
        "📞 Hỗ trợ: <a href='tg://user?id=8842938928'>Nhắn admin</a>",
        parse_mode="HTML"
    )


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User confirms payment — forward to admin."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    plan = db.get_user_plan(chat_id)

    if plan == "premium":
        await update.message.reply_text("💎 Tài khoản của bạn đã là Premium rồi!")
        return

    if ADMIN_CHAT_ID:
        admin_msg = (
            f"💳 <b>Yêu cầu nâng cấp Premium</b>\n\n"
            f"User: {user.first_name} (@{user.username or 'N/A'})\n"
            f"Chat ID: <code>{chat_id}</code>\n\n"
            f"Để kích hoạt, dùng lệnh:\n"
            f"<code>/approve {chat_id}</code>"
        )
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_msg,
            parse_mode="HTML"
        )

    await update.message.reply_text(
        "✅ Đã gửi yêu cầu xác nhận!\n\n"
        "Admin sẽ kích hoạt Premium cho bạn trong vòng 24h.\n"
        "Nếu bạn đã gửi ảnh bill, hãy đảm bảo gửi kèm trong cùng tin nhắn này hoặc nhắn riêng cho admin.\n\n"
        f"📞 Liên hệ: <a href='tg://user?id={ADMIN_CHAT_ID}'>Nhắn admin</a>",
        parse_mode="HTML"
    )


async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to approve premium for a user."""
    chat_id = update.effective_chat.id

    if chat_id != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ Bạn không có quyền dùng lệnh này.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Dùng: /approve [chat_id]\nVí dụ: /approve 123456789")
        return

    target_chat_id = int(context.args[0])
    db.set_user_plan(target_chat_id, "premium")

    try:
        await context.bot.send_message(
            chat_id=target_chat_id,
            text=(
                "🎉 Tài khoản của bạn đã được nâng cấp lên <b>Premium</b>!\n\n"
                "✅ HSK 2-9 đã được mở khoá\n"
                "✅ 5000+ từ vựng đầy đủ\n\n"
                "Dùng /setlevel 2 để bắt đầu HSK 2 ngay!\n\n"
                "Cảm ơn bạn đã ủng hộ HSK Bot! 🙏"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass

    await update.message.reply_text(f"✅ Đã kích hoạt Premium cho chat_id: {target_chat_id}")


async def revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to revoke premium."""
    chat_id = update.effective_chat.id

    if chat_id != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ Bạn không có quyền dùng lệnh này.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Dùng: /revoke [chat_id]")
        return

    target_chat_id = int(context.args[0])
    db.set_user_plan(target_chat_id, "basic")
    await update.message.reply_text(f"✅ Đã thu hồi Premium của chat_id: {target_chat_id}")


async def say(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send TTS pronunciation audio for a Chinese word."""
    chat_id = update.effective_chat.id
    plan = db.get_user_plan(chat_id)

    if plan != "premium":
        await update.message.reply_text(
            "🔒 Tính năng phát âm TTS dành cho Premium.\n"
            "Nhắn /premium để nâng cấp!"
        )
        return

    if not context.args:
        await update.message.reply_text("Dùng: /say [chữ Hán]\nVí dụ: /say 你好")
        return

    hanzi = context.args[0]
    audio = get_pronunciation_audio(hanzi)
    if audio:
        import io
        await update.message.reply_voice(
            voice=io.BytesIO(audio),
            caption=f"🔊 Phát âm: {hanzi}"
        )
    else:
        await update.message.reply_text("❌ Không thể tạo audio lúc này. Thử lại sau!")


async def mocktest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a 20-question HSK mock test."""
    chat_id = update.effective_chat.id
    plan = db.get_user_plan(chat_id)

    if plan != "premium":
        await update.message.reply_text(
            "🔒 Mock test dành cho Premium.\n"
            "Nhắn /premium để nâng cấp!"
        )
        return

    sub = db.get_subscriber(chat_id)
    if not sub:
        await update.message.reply_text("Bạn chưa đăng ký. Nhắn /start trước!")
        return

    level = sub["current_hsk_level"]
    questions = generate_mock_test(level, num_questions=10)

    if not questions:
        await update.message.reply_text("Không đủ từ để tạo mock test. Thử /setlevel khác!")
        return

    all_words = get_all_words()
    await update.message.reply_text(
        f"📝 <b>Mock Test HSK {level}</b> — 10 câu\n"
        "Trả lời các câu hỏi bên dưới. Kết quả sẽ tổng kết sau!",
        parse_mode="HTML"
    )

    # Store test session in context
    context.user_data["mocktest_total"] = len(questions)
    context.user_data["mocktest_correct"] = 0
    context.user_data["mocktest_answered"] = 0
    context.user_data["in_mocktest"] = True

    for q in questions:
        await _send_quiz(update.message, chat_id, q["word"], all_words)


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
        f"❓ Quiz: Chữ <b>{word['hanzi']}</b> ({word['pinyin']}) — HSK {word['hsk_level']}\n"
        f"Nghĩa là gì?"
    )
    await message.reply_text(quiz_text, reply_markup=reply_markup, parse_mode="HTML")


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
            f"✅ Đúng rồi! <b>{hanzi}</b> = {word['meaning'] if word else '?'}\n"
            f"🔥 Streak: {streak} ngày"
        )
    else:
        correct_label = labels[correct_idx]
        correct_meaning = word["meaning"] if word else "?"
        response = (
            f"❌ Sai rồi. Đáp án đúng: <b>{correct_label}. {correct_meaning}</b>\n"
            f"Sẽ ôn lại ngày mai 📅"
        )

    await query.edit_message_text(
        text=f"{query.message.text}\n\n{response}",
        parse_mode="HTML",
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
    app.add_handler(CommandHandler("premium", premium))
    app.add_handler(CommandHandler("confirm", confirm))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("revoke", revoke))
    app.add_handler(CommandHandler("say", say))
    app.add_handler(CommandHandler("mocktest", mocktest))

    # Start Casso webhook server in background thread
    port_str = os.environ.get("PORT", "")
    logger.info(f"PORT env var = '{port_str}'")
    try:
        port = int(port_str) if port_str else 8000
        import uvicorn
        from webhook import app as webhook_app

        def run_webhook():
            try:
                logger.info(f"Uvicorn starting on 0.0.0.0:{port}")
                uvicorn.run(webhook_app, host="0.0.0.0", port=port, log_level="info")
            except Exception as e:
                logger.error(f"Uvicorn failed: {e}")

        t = threading.Thread(target=run_webhook, daemon=True)
        t.start()
        logger.info(f"Webhook thread started on port {port}")
    except Exception as e:
        logger.error(f"Failed to start webhook server: {e}")

    logger.info("Bot started. Polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

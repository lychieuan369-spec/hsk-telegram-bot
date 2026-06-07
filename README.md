# HSK Daily Telegram Bot

Học tiếng Trung mỗi ngày qua Telegram với chiết tự chữ Hán, được tạo tự động bởi Claude AI.

---

## Tính năng

- 📖 Bài học mỗi ngày lúc 7h sáng (giờ Việt Nam)
- 🔍 Chiết tự chữ Hán — phân tích bộ thủ, nguồn gốc, mnemonic
- ❓ Quiz trắc nghiệm A/B/C/D với spaced repetition
- 📊 Theo dõi tiến độ, streak, độ chính xác
- 🎯 Hỗ trợ HSK 1–6

---

## Cài đặt nhanh

### 1. Lấy Telegram Bot Token

1. Nhắn tin [@BotFather](https://t.me/BotFather) trên Telegram
2. Gõ `/newbot`, đặt tên và username cho bot
3. Sao chép token dạng `123456789:ABCdef...`

### 2. Lấy Anthropic API Key

Đăng ký tại [console.anthropic.com](https://console.anthropic.com) và tạo API key.

### 3. Tạo Supabase Database (khuyến nghị cho production)

1. Vào [supabase.com](https://supabase.com), tạo project mới (free tier)
2. Vào **Settings → Database → Connection string → URI**
3. Sao chép chuỗi dạng: `postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres`

> **Phase 1 (local/Railway only):** Nếu chưa có Supabase, bỏ qua `DATABASE_URL` — bot sẽ dùng SQLite file `hsk_bot.db` tự động.  
> ⚠️ Khi đó GitHub Actions sẽ không truy cập được DB của Railway — chỉ dùng Railway để chạy bot.py + daily_lesson.py trong cùng container.

---

## Deploy Bot lên Railway

1. Fork/push repo này lên GitHub
2. Vào [railway.app](https://railway.app), tạo project mới → **Deploy from GitHub repo**
3. Chọn repo vừa push
4. Vào **Variables**, thêm:
   - `BOT_TOKEN` = token từ BotFather
   - `ANTHROPIC_API_KEY` = key từ Anthropic
   - `DATABASE_URL` = chuỗi kết nối PostgreSQL (Supabase)
5. Railway tự build và chạy `python bot.py` theo `railway.json`

---

## Cấu hình GitHub Actions (gửi bài học hàng ngày)

GitHub Actions chạy `daily_lesson.py` mỗi ngày lúc 7h sáng VN (00:00 UTC).

1. Vào repo GitHub → **Settings → Secrets and variables → Actions**
2. Thêm 3 secrets:
   - `BOT_TOKEN`
   - `ANTHROPIC_API_KEY`
   - `DATABASE_URL` (Supabase PostgreSQL URI)

Trigger thủ công: Vào tab **Actions → HSK Daily Lesson → Run workflow**

---

## Lệnh bot

| Lệnh | Mô tả |
|------|-------|
| `/start` | Đăng ký nhận bài học, xem cấp độ hiện tại |
| `/stop` | Dừng nhận bài học |
| `/progress` | Xem tiến độ, streak, độ chính xác |
| `/review` | Ôn tập 5 từ đang đến hạn (spaced repetition) |
| `/quiz` | Quiz từ hôm nay |
| `/setlevel 1-6` | Đổi cấp độ HSK |

---

## Kiến trúc

```
Railway (24/7)              GitHub Actions (cron 7h/ngày)
┌─────────────┐             ┌───────────────────────────┐
│   bot.py    │             │      daily_lesson.py       │
│  (polling)  │             │  (one-shot, stateless)    │
└──────┬──────┘             └───────────┬───────────────┘
       │                                │
       └──────────┬─────────────────────┘
                  ▼
         Supabase PostgreSQL
         (subscribers, quiz_history, streak)
                  │
                  ▼
         Claude Haiku API
         (chiết tự content)
```

---

## Spaced Repetition Logic

| Kết quả quiz | Ôn lại sau |
|-------------|-----------|
| Sai | 1 ngày |
| Đúng lần 1 | 3 ngày |
| Đúng lần 2+ | 7 ngày |

---

## Phát triển local

```bash
# Cài dependencies
pip install -r requirements.txt

# Set env vars
export BOT_TOKEN="your_token"
export ANTHROPIC_API_KEY="your_key"
# DATABASE_URL để trống → dùng SQLite local (hsk_bot.db)

# Chạy bot
python bot.py

# Test gửi lesson thủ công
python daily_lesson.py
```

---

## Cấu trúc files

```
hsk_telegram_bot/
├── bot.py               # Bot chính (Railway worker)
├── daily_lesson.py      # Script GitHub Actions
├── database.py          # SQLite + PostgreSQL dual support
├── hsk_words.py         # Từ điển HSK 1-6 (180+ từ)
├── content_generator.py # Claude API chiết tự
├── requirements.txt
├── Procfile             # Railway config
├── railway.json         # Railway deploy config
└── .github/
    └── workflows/
        └── hsk-daily.yml
```

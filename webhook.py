import os
import re
import hmac
import hashlib
import logging
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

BOT_TOKEN = "8738410189:AAHVBb50cGSk4-GAhcwWl-6f9LC8huhz6M8"
CASSO_SECRET_TOKEN = os.environ.get("CASSO_SECRET_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
MIN_AMOUNT = 59000


def verify_sig(header_sig: str, body: bytes, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, header_sig)


def send_telegram(chat_id, text):
    try:
        resp = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"sendMessage failed chat_id={chat_id}: {e}")


@app.post("/webhook/casso")
async def casso_webhook(request: Request):
    body = await request.body()

    if CASSO_SECRET_TOKEN:
        sig = request.headers.get("X-Casso-Signature", "")
        if not verify_sig(sig, body, CASSO_SECRET_TOKEN):
            logger.warning("Invalid Casso signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    import json
    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    transactions = payload.get("data", [])
    processed = []

    for txn in transactions:
        txn_id = txn.get("id")
        amount = txn.get("amount", 0)
        description = txn.get("description", "")
        when = txn.get("when", "")
        tid = txn.get("tid", "")

        logger.info(f"Transaction id={txn_id} tid={tid} amount={amount} desc={description!r}")

        if amount < MIN_AMOUNT:
            logger.info(f"Skipped id={txn_id}: amount {amount} < {MIN_AMOUNT}")
            continue

        match = re.search(r"HSK\s+(\d{6,12})", description, re.IGNORECASE)
        if not match:
            logger.info(f"No chat_id match in desc: {description!r}")
            if ADMIN_CHAT_ID:
                send_telegram(
                    ADMIN_CHAT_ID,
                    f"[Casso] Giao dịch không khớp HSK\nID: {txn_id} | {tid}\nSố tiền: {amount:,} VND\nNội dung: {description}\nThời gian: {when}",
                )
            continue

        chat_id = int(match.group(1))
        db.set_user_plan(chat_id, "premium")
        logger.info(f"Set premium for chat_id={chat_id} txn={txn_id}")

        send_telegram(
            chat_id,
            "🎉 Premium đã được kích hoạt tự động! Dùng /setlevel 2 để bắt đầu HSK 2 ngay.",
        )

        if ADMIN_CHAT_ID:
            send_telegram(
                ADMIN_CHAT_ID,
                f"[Casso] Premium kích hoạt\nChat ID: {chat_id}\nID: {txn_id} | {tid}\nSố tiền: {amount:,} VND\nNội dung: {description}\nThời gian: {when}",
            )

        processed.append({"txn_id": txn_id, "chat_id": chat_id, "amount": amount})

    return JSONResponse({"status": "ok", "processed": processed})


@app.get("/health")
async def health():
    return {"status": "ok"}

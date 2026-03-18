from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import httpx
import time
import secrets
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "bot_data.db"
ADMIN_PASSWORD = "NEVERBOT"

# ═══════════════════════════════════════════
# 🔑 КОНФИГУРАЦИЯ — ЗАПОЛНИ СВОИ ДАННЫЕ
# ═══════════════════════════════════════════
BOT_TOKEN = "8688501814:AAGxO3NBVsTG-LLXXr5GrcEuy6vAbAiFuBc"  # ← Токен твоего бота
STARS_PROVIDER_TOKEN = ""  # Для Stars оставляем пустым
ADMIN_CHAT_ID = 8565986003  # ← Твой Telegram ID для уведомлений

# Реквизиты для ручной оплаты (TON / СБП)
PAYMENT_CONFIG = {
    "ton": {
        "wallet": "UQBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "comment": "Укажите ID в комментарии к переводу",
    },
    "sbp": {
        "bank": "Сбербанк",
        "phone": "+7 (937) 124-38-45",
        "recipient": "Альфия И.",
    },
}


# ═══════════════════════════════════════════
# 🗄️ DATABASE
# ═══════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Создаём таблицы при старте (если их нет)."""
    conn = get_db()
    # Основная таблица пользователей (уже существует у тебя)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance TEXT DEFAULT '0.00',
            payments INTEGER DEFAULT 0,
            suscefylu_payments INTEGER DEFAULT 0
        )
    """)
    # Таблица заявок на пополнение
    conn.execute("""
        CREATE TABLE IF NOT EXISTS topup_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            method TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            request_code TEXT,
            created_at INTEGER,
            reviewed_at INTEGER,
            reviewed_by TEXT,
            note TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    # Таблица платежей Stars (для отслеживания)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stars_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            telegram_payment_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at INTEGER,
            completed_at INTEGER
        )
    """)
    conn.commit()
    conn.close()


# Инициализируем БД при старте
init_db()


# ═══════════════════════════════════════════
# 📋 МОДЕЛИ
# ═══════════════════════════════════════════
class UserProfile(BaseModel):
    user_id: int
    balance: str
    suscefylu_payments: int
    payments: int


class BuyRequest(BaseModel):
    user_id: int
    price: float


class TopUpStarsRequest(BaseModel):
    user_id: int
    amount: float


class TopUpManualRequest(BaseModel):
    user_id: int
    amount: float
    method: str  # "ton" или "sbp"


class TopUpConfirmRequest(BaseModel):
    user_id: int
    amount: float
    method: str


class AdminTopUpAction(BaseModel):
    password: str
    request_id: int
    action: str  # "approve" или "reject"
    note: Optional[str] = None


# ═══════════════════════════════════════════
# 🔧 HELPERS
# ═══════════════════════════════════════════
async def send_telegram_message(chat_id: int, text: str):
    """Отправляет сообщение через Telegram Bot API."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
            })
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")


async def notify_admin_new_topup(user_id: int, amount: float, method: str, request_code: str):
    """Уведомляет админа о новой заявке на пополнение."""
    method_names = {"ton": "💎 TON", "sbp": "🏦 СБП"}
    text = (
        f"🔔 <b>Новая заявка на пополнение</b>\n\n"
        f"👤 Пользователь: <code>{user_id}</code>\n"
        f"💰 Сумма: <b>{amount} ₽</b>\n"
        f"📱 Способ: {method_names.get(method, method)}\n"
        f"🔑 Код заявки: <code>{request_code}</code>\n\n"
        f"Для подтверждения:\n"
        f"<code>/approve {request_code}</code>\n\n"
        f"Для отклонения:\n"
        f"<code>/reject {request_code}</code>"
    )
    await send_telegram_message(ADMIN_CHAT_ID, text)


def ensure_user_exists(conn, user_id: int):
    """Создаёт пользователя если его нет."""
    user = conn.execute(
        "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not user:
        conn.execute(
            "INSERT INTO users (user_id, balance, payments, suscefylu_payments) VALUES (?, ?, ?, ?)",
            (user_id, "0.00", 0, 0),
        )
        conn.commit()


def credit_balance(conn, user_id: int, amount: float):
    """Зачисляет средства на баланс пользователя."""
    user = conn.execute(
        "SELECT balance FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    current_balance = float(user["balance"] or 0)
    new_balance = round(current_balance + amount, 2)

    conn.execute(
        "UPDATE users SET balance = ? WHERE user_id = ?",
        (str(new_balance), user_id),
    )
    conn.commit()
    return new_balance


# ═══════════════════════════════════════════
# 📌 СУЩЕСТВУЮЩИЕ ЭНДПОИНТЫ (без изменений)
# ═══════════════════════════════════════════
@app.get("/api/profile/{user_id}", response_model=UserProfile)
async def get_profile(user_id: int):
    conn = get_db()
    try:
        user = conn.execute(
            "SELECT user_id, balance, payments, suscefylu_payments FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if user:
            return {
                "user_id": user["user_id"],
                "balance": user["balance"],
                "suscefylu_payments": user["suscefylu_payments"],
                "payments": user["payments"],
            }
        else:
            conn.execute(
                "INSERT INTO users (user_id, balance, payments, suscefylu_payments) VALUES (?, ?, ?, ?)",
                (user_id, "0.00", 0, 0),
            )
            conn.commit()
            return {
                "user_id": user_id,
                "balance": "0.00",
                "suscefylu_payments": 0,
                "payments": 0,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/buy")
async def buy_product(data: BuyRequest):
    conn = get_db()
    try:
        user = conn.execute(
            "SELECT balance, payments, suscefylu_payments FROM users WHERE user_id = ?",
            (data.user_id,),
        ).fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        current_balance = float(user["balance"] or 0)
        current_payments = int(user["payments"] or 0)
        current_sysc = int(user["suscefylu_payments"] or 0)

        if current_balance < data.price:
            raise HTTPException(status_code=400, detail="Недостаточно средств")

        new_balance = round(current_balance - data.price, 2)
        new_payments = current_payments + int(data.price)
        new_sysc = current_sysc + 1

        conn.execute(
            "UPDATE users SET balance = ?, payments = ?, suscefylu_payments = ? WHERE user_id = ?",
            (str(new_balance), new_payments, new_sysc, data.user_id),
        )
        conn.commit()

        print(f"User {data.user_id} bought: Balance {new_balance}, Deals {new_sysc}")

        return {
            "status": "success",
            "new_balance": str(new_balance),
            "payments": new_payments,
            "suscefylu_payments": new_sysc,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error during buy: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ═══════════════════════════════════════════
# 💫 STARS — Автоматическое пополнение
# ═══════════════════════════════════════════
@app.post("/api/topup/stars")
async def topup_stars(data: TopUpStarsRequest):
    """
    Создаёт инвойс Telegram Stars.
    Фронтенд вызывает tg.openInvoice(invoice_url, callback).
    """
    if data.amount < 1:
        raise HTTPException(status_code=400, detail="Минимальная сумма: 1 ₽")

    conn = get_db()
    try:
        ensure_user_exists(conn, data.user_id)

        # Создаём инвойс через Bot API
        # Для Stars: 1 Star ≈ стоимость определяется Telegram
        # Мы передаём цену в "копейках Stars" (1 Star = 100)
        stars_amount = max(1, int(data.amount))  # Минимум 1 Star

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/createInvoiceLink"
        payload = {
            "title": f"Пополнение баланса",
            "description": f"Пополнение на {data.amount} ₽ для аккаунта {data.user_id}",
            "payload": f"topup_{data.user_id}_{data.amount}_{int(time.time())}",
            "currency": "XTR",  # XTR = Telegram Stars
            "prices": [
                {
                    "label": f"Пополнение {data.amount} ₽",
                    "amount": stars_amount,
                }
            ],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            result = response.json()

        if not result.get("ok"):
            error_desc = result.get("description", "Unknown error")
            print(f"Stars invoice error: {error_desc}")
            raise HTTPException(
                status_code=500,
                detail=f"Не удалось создать платёж: {error_desc}",
            )

        invoice_url = result["result"]

        # Сохраняем запись о платеже
        conn.execute(
            """INSERT INTO stars_payments 
               (user_id, amount, status, created_at) 
               VALUES (?, ?, 'pending', ?)""",
            (data.user_id, data.amount, int(time.time())),
        )
        conn.commit()

        print(f"Stars invoice created for user {data.user_id}: {data.amount} ₽")

        return {
            "status": "invoice_created",
            "invoice_url": invoice_url,
            "amount": data.amount,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Stars topup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/topup/stars/confirm")
async def confirm_stars_payment(data: TopUpStarsRequest):
    """
    Вызывается после успешной оплаты Stars (callback status === 'paid').
    Зачисляет баланс пользователю.
    """
    conn = get_db()
    try:
        ensure_user_exists(conn, data.user_id)

        # Зачисляем баланс
        new_balance = credit_balance(conn, data.user_id, data.amount)

        # Обновляем запись Stars-платежа
        conn.execute(
            """UPDATE stars_payments 
               SET status = 'completed', completed_at = ? 
               WHERE user_id = ? AND amount = ? AND status = 'pending'
               ORDER BY created_at DESC LIMIT 1""",
            (int(time.time()), data.user_id, data.amount),
        )
        conn.commit()

        print(f"Stars payment confirmed: user {data.user_id}, +{data.amount} ₽, new balance: {new_balance}")

        # Уведомляем админа
        await send_telegram_message(
            ADMIN_CHAT_ID,
            f"✅ <b>Stars оплата</b>\n\n"
            f"👤 ID: <code>{data.user_id}</code>\n"
            f"💰 Сумма: <b>{data.amount} ₽</b>\n"
            f"💳 Новый баланс: <b>{new_balance} ₽</b>\n\n"
            f"Зачислено автоматически ✨",
        )

        return {
            "status": "success",
            "new_balance": str(new_balance),
            "amount": data.amount,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Stars confirm error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ═══════════════════════════════════════════
# 💎🏦 MANUAL — TON & СБП (ручная проверка)
# ═══════════════════════════════════════════
@app.post("/api/topup/manual")
async def topup_manual(data: TopUpManualRequest):
    """
    Создаёт заявку на ручное пополнение (TON или СБП).
    Админ получает уведомление и подтверждает вручную.
    """
    if data.method not in ("ton", "sbp"):
        raise HTTPException(status_code=400, detail="Неверный метод оплаты")

    if data.amount < 10:
        raise HTTPException(status_code=400, detail="Минимальная сумма: 10 ₽")

    conn = get_db()
    try:
        ensure_user_exists(conn, data.user_id)

        # Проверяем нет ли уже активной заявки
        existing = conn.execute(
            """SELECT id FROM topup_requests 
               WHERE user_id = ? AND status = 'pending' 
               ORDER BY created_at DESC LIMIT 1""",
            (data.user_id,),
        ).fetchone()

        if existing:
            raise HTTPException(
                status_code=409,
                detail="У вас уже есть активная заявка на пополнение. Дождитесь её обработки.",
            )

        # Генерируем уникальный код заявки
        request_code = secrets.token_hex(4).upper()  # Например: "A3F2B1C9"

        conn.execute(
            """INSERT INTO topup_requests 
               (user_id, amount, method, status, request_code, created_at)
               VALUES (?, ?, ?, 'pending', ?, ?)""",
            (data.user_id, data.amount, data.method, request_code, int(time.time())),
        )
        conn.commit()

        print(f"Manual topup request: user {data.user_id}, {data.amount} ₽, method: {data.method}, code: {request_code}")

        # Уведомляем админа
        await notify_admin_new_topup(data.user_id, data.amount, data.method, request_code)

        return {
            "status": "pending",
            "request_code": request_code,
            "message": "Заявка создана. Ожидайте подтверждения.",
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Manual topup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/topup/status/{user_id}")
async def get_topup_status(user_id: int):
    """Проверяет статус последней заявки пользователя."""
    conn = get_db()
    try:
        request = conn.execute(
            """SELECT id, amount, method, status, request_code, created_at, note
               FROM topup_requests 
               WHERE user_id = ? 
               ORDER BY created_at DESC LIMIT 1""",
            (user_id,),
        ).fetchone()

        if not request:
            return {"status": "none", "message": "Нет заявок"}

        return {
            "id": request["id"],
            "amount": request["amount"],
            "method": request["method"],
            "status": request["status"],
            "request_code": request["request_code"],
            "created_at": request["created_at"],
            "note": request["note"],
        }
    finally:
        conn.close()


@app.get("/api/topup/history/{user_id}")
async def get_topup_history(user_id: int):
    """Возвращает историю всех пополнений пользователя."""
    conn = get_db()
    try:
        requests = conn.execute(
            """SELECT id, amount, method, status, request_code, created_at, reviewed_at, note
               FROM topup_requests 
               WHERE user_id = ? 
               ORDER BY created_at DESC
               LIMIT 50""",
            (user_id,),
        ).fetchall()

        stars = conn.execute(
            """SELECT id, amount, status, created_at, completed_at
               FROM stars_payments 
               WHERE user_id = ? 
               ORDER BY created_at DESC
               LIMIT 50""",
            (user_id,),
        ).fetchall()

        return {
            "manual": [dict(r) for r in requests],
            "stars": [dict(s) for s in stars],
        }
    finally:
        conn.close()


# ═══════════════════════════════════════════
# 🔑 ADMIN — Управление пополнениями
# ═══════════════════════════════════════════

@app.get("/api/admin/{password}/pending")
async def admin_list_pending(password: str):
    """Список всех ожидающих заявок на пополнение."""
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    conn = get_db()
    try:
        requests = conn.execute(
            """SELECT tr.*, u.balance as current_balance
               FROM topup_requests tr
               LEFT JOIN users u ON tr.user_id = u.user_id
               WHERE tr.status = 'pending'
               ORDER BY tr.created_at ASC"""
        ).fetchall()

        return {
            "count": len(requests),
            "requests": [dict(r) for r in requests],
        }
    finally:
        conn.close()


@app.post("/api/admin/topup/action")
async def admin_topup_action(data: AdminTopUpAction):
    """
    Админ подтверждает или отклоняет заявку на пополнение.
    action: "approve" — зачисляет деньги
    action: "reject"  — отклоняет заявку
    """
    if data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    if data.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action должен быть 'approve' или 'reject'")

    conn = get_db()
    try:
        # Находим заявку
        request = conn.execute(
            "SELECT * FROM topup_requests WHERE id = ?", (data.request_id,)
        ).fetchone()

        if not request:
            raise HTTPException(status_code=404, detail="Заявка не найдена")

        if request["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Заявка уже обработана (статус: {request['status']})",
            )

        now = int(time.time())

        if data.action == "approve":
            # Зачисляем баланс
            new_balance = credit_balance(conn, request["user_id"], request["amount"])

            # Обновляем статус заявки
            conn.execute(
                """UPDATE topup_requests 
                   SET status = 'approved', reviewed_at = ?, reviewed_by = 'admin', note = ?
                   WHERE id = ?""",
                (now, data.note or "Подтверждено админом", data.request_id),
            )
            conn.commit()

            print(f"Admin APPROVED topup #{data.request_id}: user {request['user_id']}, +{request['amount']} ₽")

            # Уведомляем пользователя
            await send_telegram_message(
                request["user_id"],
                f"✅ <b>Баланс пополнен!</b>\n\n"
                f"💰 Сумма: <b>+{request['amount']} ₽</b>\n"
                f"💳 Новый баланс: <b>{new_balance} ₽</b>\n\n"
                f"Спасибо за пополнение! 🎉",
            )

            return {
                "status": "approved",
                "user_id": request["user_id"],
                "amount": request["amount"],
                "new_balance": str(new_balance),
            }

        else:  # reject
            conn.execute(
                """UPDATE topup_requests 
                   SET status = 'rejected', reviewed_at = ?, reviewed_by = 'admin', note = ?
                   WHERE id = ?""",
                (now, data.note or "Отклонено админом", data.request_id),
            )
            conn.commit()

            print(f"Admin REJECTED topup #{data.request_id}: user {request['user_id']}")

            # Уведомляем пользователя
            reason = data.note or "Платёж не подтверждён"
            await send_telegram_message(
                request["user_id"],
                f"❌ <b>Заявка на пополнение отклонена</b>\n\n"
                f"💰 Сумма: <b>{request['amount']} ₽</b>\n"
                f"📝 Причина: {reason}\n\n"
                f"Если вы уверены, что оплатили — обратитесь в поддержку.",
            )

            return {
                "status": "rejected",
                "user_id": request["user_id"],
                "amount": request["amount"],
            }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Admin topup action error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/admin/{password}/approve/{request_code}")
async def admin_approve_by_code(password: str, request_code: str):
    """
    Быстрое подтверждение по коду заявки.
    Удобно для использования через команды бота.
    """
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    conn = get_db()
    try:
        request = conn.execute(
            "SELECT * FROM topup_requests WHERE request_code = ?",
            (request_code,),
        ).fetchone()

        if not request:
            raise HTTPException(status_code=404, detail="Заявка не найдена")

        if request["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Заявка уже обработана (статус: {request['status']})",
            )

        # Зачисляем
        new_balance = credit_balance(conn, request["user_id"], request["amount"])

        conn.execute(
            """UPDATE topup_requests 
               SET status = 'approved', reviewed_at = ?, reviewed_by = 'admin'
               WHERE request_code = ?""",
            (int(time.time()), request_code),
        )
        conn.commit()

        # Уведомляем юзера
        await send_telegram_message(
            request["user_id"],
            f"✅ <b>Баланс пополнен!</b>\n\n"
            f"💰 +{request['amount']} ₽\n"
            f"💳 Баланс: <b>{new_balance} ₽</b>",
        )

        return {
            "status": "approved",
            "user_id": request["user_id"],
            "amount": request["amount"],
            "new_balance": str(new_balance),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/admin/{password}/reject/{request_code}")
async def admin_reject_by_code(password: str, request_code: str, reason: str = "Платёж не найден"):
    """Быстрое отклонение по коду заявки."""
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    conn = get_db()
    try:
        request = conn.execute(
            "SELECT * FROM topup_requests WHERE request_code = ?",
            (request_code,),
        ).fetchone()

        if not request:
            raise HTTPException(status_code=404, detail="Заявка не найдена")

        if request["status"] != "pending":
            raise HTTPException(status_code=409, detail="Заявка уже обработана")

        conn.execute(
            """UPDATE topup_requests 
               SET status = 'rejected', reviewed_at = ?, reviewed_by = 'admin', note = ?
               WHERE request_code = ?""",
            (int(time.time()), reason, request_code),
        )
        conn.commit()

        await send_telegram_message(
            request["user_id"],
            f"❌ <b>Заявка отклонена</b>\n\n"
            f"💰 {request['amount']} ₽\n"
            f"📝 Причина: {reason}",
        )

        return {"status": "rejected", "request_code": request_code}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ═══════════════════════════════════════════
# 🔑 ADMIN — Существующие эндпоинты
# ═══════════════════════════════════════════
@app.get("/api/admin/{password}/set_balance/{amount}/{user_id}")
async def admin_set_balance(password: str, amount: str, user_id: int):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    conn = get_db()
    conn.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    return {"status": "success", "new_balance": amount}


@app.get("/api/admin/{password}/set_payments/{amount}/{user_id}")
async def admin_set_payments(password: str, amount: int, user_id: int):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    conn = get_db()
    conn.execute("UPDATE users SET payments = ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    return {"status": "success", "payments": amount}


@app.get("/api/admin/{password}/set_sysc_payments/{amount}/{user_id}")
async def admin_set_sysc(password: str, amount: int, user_id: int):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    conn = get_db()
    conn.execute(
        "UPDATE users SET suscefylu_payments = ? WHERE user_id = ?",
        (amount, user_id),
    )
    conn.commit()
    conn.close()
    return {"status": "success", "suscefylu_payments": amount}


@app.get("/api/admin/{password}/stats")
async def admin_stats(password: str):
    """Общая статистика для админа."""
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    conn = get_db()
    try:
        users_count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        total_balance = conn.execute(
            "SELECT COALESCE(SUM(CAST(balance AS REAL)), 0) as s FROM users"
        ).fetchone()["s"]
        pending_topups = conn.execute(
            "SELECT COUNT(*) as c FROM topup_requests WHERE status = 'pending'"
        ).fetchone()["c"]
        approved_topups = conn.execute(
            "SELECT COUNT(*) as c, COALESCE(SUM(amount), 0) as s FROM topup_requests WHERE status = 'approved'"
        ).fetchone()
        stars_completed = conn.execute(
            "SELECT COUNT(*) as c, COALESCE(SUM(amount), 0) as s FROM stars_payments WHERE status = 'completed'"
        ).fetchone()

        return {
            "users_count": users_count,
            "total_balance": round(total_balance, 2),
            "pending_topups": pending_topups,
            "approved_topups": {
                "count": approved_topups["c"],
                "total": round(approved_topups["s"], 2),
            },
            "stars_payments": {
                "count": stars_completed["c"],
                "total": round(stars_completed["s"], 2),
            },
        }
    finally:
        conn.close()


# ═══════════════════════════════════════════
# 📡 WEBHOOK для Telegram (Stars callback)
# ═══════════════════════════════════════════
@app.post("/api/webhook/telegram")
async def telegram_webhook(update: dict):
    """
    Webhook для обработки successful_payment от Telegram.
    Telegram шлёт это когда Stars-оплата прошла.
    """
    try:
        # Проверяем pre_checkout_query (обязательно отвечать!)
        if "pre_checkout_query" in update:
            query = update["pre_checkout_query"]
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerPreCheckoutQuery"
            async with httpx.AsyncClient() as client:
                await client.post(url, json={
                    "pre_checkout_query_id": query["id"],
                    "ok": True,
                })
            return {"ok": True}

        # Обработка successful_payment
        message = update.get("message", {})
        payment = message.get("successful_payment")

        if payment:
            user_id = message.get("from", {}).get("id")
            payload = payment.get("invoice_payload", "")
            telegram_payment_id = payment.get("telegram_payment_charge_id", "")

            # Парсим payload: "topup_{user_id}_{amount}_{timestamp}"
            parts = payload.split("_")
            if len(parts) >= 3 and parts[0] == "topup":
                amount = float(parts[2])

                conn = get_db()
                try:
                    ensure_user_exists(conn, user_id)
                    new_balance = credit_balance(conn, user_id, amount)

                    # Обновляем stars_payments
                    conn.execute(
                        """UPDATE stars_payments 
                           SET status = 'completed', telegram_payment_id = ?, completed_at = ?
                           WHERE user_id = ? AND status = 'pending'
                           ORDER BY created_at DESC LIMIT 1""",
                        (telegram_payment_id, int(time.time()), user_id),
                    )
                    conn.commit()

                    print(f"Webhook: Stars payment confirmed for user {user_id}, +{amount} ₽")

                    # Уведомляем админа
                    await send_telegram_message(
                        ADMIN_CHAT_ID,
                        f"⭐ <b>Stars оплата (webhook)</b>\n\n"
                        f"👤 ID: <code>{user_id}</code>\n"
                        f"💰 +{amount} ₽\n"
                        f"💳 Баланс: {new_balance} ₽\n"
                        f"🆔 Payment: <code>{telegram_payment_id}</code>",
                    )
                finally:
                    conn.close()

        return {"ok": True}

    except Exception as e:
        print(f"Webhook error: {e}")
        return {"ok": True}  # Всегда отвечаем 200 чтобы Telegram не ретраил


# ═══════════════════════════════════════════
# 🏥 HEALTH CHECK
# ═══════════════════════════════════════════
@app.get("/")
async def health():
    return {
        "status": "running",
        "service": "ЯСПЛИТ API",
        "version": "2.0.0",
    }


@app.get("/api/health")
async def health_detailed():
    conn = get_db()
    try:
        users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        pending = conn.execute(
            "SELECT COUNT(*) as c FROM topup_requests WHERE status = 'pending'"
        ).fetchone()["c"]
        return {
            "status": "healthy",
            "users": users,
            "pending_topups": pending,
        }
    finally:
        conn.close()
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "bot_data.db"
ADMIN_PASSWORD = "NEVERBOT"  # ЗАМЕНИ ЭТО


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class UserProfile(BaseModel):
    user_id: int
    balance: str
    suscefylu_payments: int
    payments: int

class BuyRequest(BaseModel):
    user_id: int
    price: float


@app.post("/api/buy")
async def buy_product(data: BuyRequest):
    conn = get_db_connection()
    try:
        # 1. Получаем текущие данные юзера
        user = conn.execute(
            "SELECT balance, payments, suscefylu_payments FROM users WHERE user_id = ?",
            (data.user_id,)
        ).fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        current_balance = float(user["balance"])
        current_payments = int(user["payments"])
        current_sysc = int(user["suscefylu_payments"])

        # 2. Проверяем, хватает ли денег
        if current_balance < data.price:
            raise HTTPException(status_code=400, detail="Недостаточно средств на балансе")

        # 3. Считаем новые значения
        new_balance = current_balance - data.price
        new_payments = current_payments + data.price
        new_sysc = current_sysc + 1

        # 4. Обновляем все 3 колонки сразу
        conn.execute(
            """
            UPDATE users 
            SET balance = ?, payments = ?, suscefylu_payments = ? 
            WHERE user_id = ?
            """,
            (str(new_balance), int(new_payments), new_sysc, data.user_id)
        )
        conn.commit()

        return {
            "status": "success",
            "new_balance": str(new_balance),
            "total_spent": new_payments,
            "total_deals": new_sysc
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/profile/{user_id}", response_model=UserProfile)
async def get_profile(user_id: int):
    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT user_id, balance, payments, suscefylu_payments FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        if user:
            return {
                "user_id": user["user_id"],
                "balance": user["balance"],
                "suscefylu_payments": user["suscefylu_payments"],
                "payments": user["payments"]
            }
        else:
            conn.execute(
                "INSERT INTO users (user_id, balance, payments, suscefylu_payments) VALUES (?, ?, ?, ?)",
                (user_id, "0.00", 0, 0)
            )
            conn.commit()
            return {
                "user_id": user_id, "balance": "0.00", "successful_deals": 0, "payments": 0
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ═══════════════════════════════════════════════
# ADMIN ENDPOINT: СМЕНА БАЛАНСА
# ═══════════════════════════════════════════════
@app.get("/api/admin/{password}/set_balance/{amount}/{user_id}")
async def admin_set_balance(password: str, amount: str, user_id: int):
    # 1. Проверка пароля
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Доступ запрещен: неверный пароль")

    conn = get_db_connection()
    try:
        # 2. Проверяем, существует ли пользователь
        user = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # 3. Обновляем баланс (в базе он TEXT)
        conn.execute(
            "UPDATE users SET balance = ? WHERE user_id = ?",
            (amount, user_id)
        )
        conn.commit()

        return {
            "status": "success",
            "user_id": user_id,
            "new_balance": amount
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/admin/{password}/set_payments/{amount}/{user_id}")
async def admin_set_balance(password: str, amount: str, user_id: int):
    # 1. Проверка пароля
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Доступ запрещен: неверный пароль")

    conn = get_db_connection()
    try:
        # 2. Проверяем, существует ли пользователь
        user = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # 3. Обновляем баланс (в базе он TEXT)
        conn.execute(
            "UPDATE users SET payments = ? WHERE user_id = ?",
            (amount, user_id)
        )
        conn.commit()

        return {
            "status": "success",
            "user_id": user_id,
            "payments": amount
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/admin/{password}/set_sysc_payments/{amount}/{user_id}")
async def admin_set_balance(password: str, amount: str, user_id: int):
    # 1. Проверка пароля
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Доступ запрещен: неверный пароль")

    conn = get_db_connection()
    try:
        # 2. Проверяем, существует ли пользователь
        user = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # 3. Обновляем баланс (в базе он TEXT)
        conn.execute(
            "UPDATE users SET suscefylu_payments = ? WHERE user_id = ?",
            (amount, user_id)
        )
        conn.commit()

        return {
            "status": "success",
            "user_id": user_id,
            "suscefylu_payments": amount
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
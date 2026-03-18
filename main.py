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
ADMIN_PASSWORD = "NEVERBOT"


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
        user = conn.execute(
            "SELECT balance, payments, suscefylu_payments FROM users WHERE user_id = ?",
            (data.user_id,)
        ).fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Используем .get() или проверяем на None, чтобы не прибавить к пустоте
        current_balance = float(user["balance"] or 0)
        current_payments = int(user["payments"] or 0)
        current_sysc = int(user["suscefylu_payments"] or 0)

        if current_balance < data.price:
            raise HTTPException(status_code=400, detail="Недостаточно средств")

        new_balance = round(current_balance - data.price, 2)
        new_payments = current_payments + int(data.price)
        new_sysc = current_sysc + 1 # Вот тут мы железно прибавляем 1

        conn.execute(
            """
            UPDATE users 
            SET balance = ?, payments = ?, suscefylu_payments = ? 
            WHERE user_id = ?
            """,
            (str(new_balance), new_payments, new_sysc, data.user_id)
        )
        conn.commit()

        # Проверим, что вернуло после сохранения (для отладки в логах Render)
        print(f"User {data.user_id} updated: Balance {new_balance}, Sysc {new_sysc}")

        return {
            "status": "success",
            "new_balance": str(new_balance),
            "payments": new_payments,
            "suscefylu_payments": new_sysc
        }
    except Exception as e:
        print(f"Error during buy: {e}") # Увидим ошибку в логах Render
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
                "user_id": user_id,
                "balance": "0.00",
                "suscefylu_payments": 0,
                "payments": 0
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# Админ-эндпоинты с уникальными именами функций
@app.get("/api/admin/{password}/set_balance/{amount}/{user_id}")
async def admin_set_balance(password: str, amount: str, user_id: int):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    conn = get_db_connection()
    conn.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    return {"status": "success", "new_balance": amount}


@app.get("/api/admin/{password}/set_payments/{amount}/{user_id}")
async def admin_set_payments(password: str, amount: int, user_id: int):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    conn = get_db_connection()
    conn.execute("UPDATE users SET payments = ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    return {"status": "success", "payments": amount}


@app.get("/api/admin/{password}/set_sysc_payments/{amount}/{user_id}")
async def admin_set_sysc(password: str, amount: int, user_id: int):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    conn = get_db_connection()
    conn.execute("UPDATE users SET suscefylu_payments = ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    return {"status": "success", "suscefylu_payments": amount}
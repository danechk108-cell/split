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


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class UserProfile(BaseModel):
    user_id: int
    balance: str
    successful_deals: int
    payments: int


@app.get("/api/profile/{user_id}", response_model=UserProfile)
async def get_profile(user_id: int):
    conn = get_db_connection()
    try:
        # Ищем юзера по твоим 4 колонкам
        user = conn.execute(
            "SELECT user_id, balance, payments, suscefylu_payments FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        if user:
            return {
                "user_id": user["user_id"],
                "balance": user["balance"],
                "successful_deals": user["suscefylu_payments"],
                "payments": user["payments"]
            }
        else:
            # Создаем юзера строго с 4 значениями, как в БД
            conn.execute(
                """
                INSERT INTO users (user_id, balance, payments, suscefylu_payments)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, "0.00", 0, 0)
            )
            conn.commit()

            return {
                "user_id": user_id,
                "balance": "0.00",
                "successful_deals": 0,
                "payments": 0
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
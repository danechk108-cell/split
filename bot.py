import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
    MenuButtonWebApp,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    PreCheckoutQueryHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode
import httpx

# ═══════════════════════════════════════════
# 🔑 КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════
BOT_TOKEN = "8688501814:AAGxO3NBVsTG-LLXXr5GrcEuy6vAbAiFuBc"
WEBAPP_URL = "https://project-b9q2n.vercel.app/"        # URL твоего Mini App
COMMUNITY_URL = "https://t.me/YaSplitOnlines"        # Ссылка на канал/чат
SUPPORT_URL = "https://t.me/durov"        # Ссылка на поддержку
API_BASE = "https://split-fjgy.onrender.com"         # URL твоего FastAPI
ADMIN_PASSWORD = "NEVERBOT"
ADMIN_IDS = [8565986003]                               # Telegram ID админов

# Кастомные Premium эмодзи (entity_id)
# Замени на свои ID эмодзи или используй обычные
EMOJI = {
    "logo":      "⚡",     # или tg://emoji?id=5368324170671202286
    "shop":      "🛍",
    "rocket":    "🚀",
    "star":      "⭐",
    "shield":    "🛡",
    "diamond":   "💎",
    "fire":      "🔥",
    "check":     "✅",
    "crown":     "👑",
    "money":     "💰",
    "link":      "🔗",
    "wave":      "👋",
    "sparkle":   "✨",
    "globe":     "🌐",
    "heart":     "💜",
    "zap":       "⚡",
    "gift":      "🎁",
    "trophy":    "🏆",
    "key":       "🔑",
    "bell":      "🔔",
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 🎨 ТЕКСТОВЫЕ ШАБЛОНЫ
# ═══════════════════════════════════════════
async def keep_alive_ping(context: ContextTypes.DEFAULT_TYPE):
    """
    Периодически пингует бэкенд на Render, чтобы он не 'засыпал'.
    Бесплатные инстансы Render засыпают через 15 минут бездействия.
    """
    try:
        async with httpx.AsyncClient() as client:
            # Пингуем главную страницу или эндпоинт статистики
            response = await client.get(f"{API_BASE}/", timeout=10)
            if response.status_code == 200:
                logger.info(f"Keep-alive ping success: {API_BASE}")
            else:
                logger.warning(f"Keep-alive ping returned status: {response.status_code}")
    except Exception as e:
        logger.error(f"Keep-alive ping failed: {e}")

def get_welcome_text(first_name: str) -> str:
    return (
        f"{EMOJI['sparkle']} <b>Добро пожаловать в ЯСПЛИТ</b> {EMOJI['sparkle']}\n"
        f"\n"
        f"{EMOJI['wave']} Привет, <b>{first_name}</b>!\n"
        f"\n"
        f"{EMOJI['diamond']} Мы — маркетплейс премиум\n"
        f"аккаунтов с моментальной выдачей\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"\n"
        f"{EMOJI['check']} Гарантия замены 24 часа\n"
        f"{EMOJI['rocket']} Выдача за 5 минут\n"
        f"{EMOJI['shield']} Только проверенные товары\n"
        f"{EMOJI['star']} Поддержка 24/7\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"\n"
        f"{EMOJI['zap']} Нажмите кнопку ниже, чтобы\n"
        f"открыть магазин {EMOJI['fire']}"
    )


def get_welcome_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        # Главная кнопка — открыть WebApp
        [
            InlineKeyboardButton(
                text=f"{EMOJI['shop']}  Открыть магазин",
                web_app=WebAppInfo(url=WEBAPP_URL),
            )
        ],
        # Коммьюнити
        [
            InlineKeyboardButton(
                text=f"{EMOJI['globe']}  Коммьюнити",
                url=COMMUNITY_URL,
            )
        ],
    ])


# ═══════════════════════════════════════════
# 📌 HANDLERS
# ═══════════════════════════════════════════

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка /start — главное приветствие."""
    user = update.effective_user
    if not user:
        return

    # Регистрируем пользователя на бэкенде (если ещё нет)
    try:
        async with httpx.AsyncClient() as client:
            await client.get(
                f"{API_BASE}/api/profile/{user.id}",
                timeout=5,
            )
    except Exception as e:
        logger.warning(f"Failed to register user {user.id}: {e}")

    # Отправляем приветствие
    await update.message.reply_text(
        text=get_welcome_text(user.first_name),
        parse_mode=ParseMode.HTML,
        reply_markup=get_welcome_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка /help."""
    text = (
        f"{EMOJI['key']} <b>Помощь</b>\n"
        f"\n"
        f"{EMOJI['shop']} /start — Открыть магазин\n"
        f"{EMOJI['link']} /community — Наше сообщество\n"
        f"{EMOJI['bell']} /support — Связаться с поддержкой\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"\n"
        f"{EMOJI['shield']} Если у вас возникли проблемы\n"
        f"с покупкой — напишите в поддержку.\n"
        f"Мы ответим в течение 15 минут."
    )

    await update.message.reply_text(
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                text=f"{EMOJI['shop']}  Открыть магазин",
                web_app=WebAppInfo(url=WEBAPP_URL),
            )],
            [InlineKeyboardButton(
                text=f"{EMOJI['heart']}  Поддержка",
                url=SUPPORT_URL,
            )],
        ]),
    )


async def community_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка /community."""
    text = (
        f"{EMOJI['globe']} <b>Наше коммьюнити</b>\n"
        f"\n"
        f"Присоединяйтесь к нашему каналу,\n"
        f"чтобы быть в курсе:\n"
        f"\n"
        f"{EMOJI['gift']} Акций и скидок\n"
        f"{EMOJI['fire']} Новых поступлений\n"
        f"{EMOJI['trophy']} Розыгрышей\n"
        f"{EMOJI['bell']} Важных обновлений"
    )

    await update.message.reply_text(
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                text=f"{EMOJI['globe']}  Перейти в канал",
                url=COMMUNITY_URL,
            )],
        ]),
    )


async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка /support."""
    await update.message.reply_text(
        text=(
            f"{EMOJI['shield']} <b>Поддержка</b>\n"
            f"\n"
            f"Нажмите кнопку ниже, чтобы\n"
            f"связаться с нашей командой.\n"
            f"\n"
            f"Среднее время ответа: <b>~15 мин</b>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                text=f"{EMOJI['heart']}  Написать в поддержку",
                url=SUPPORT_URL,
            )],
        ]),
    )


# ═══════════════════════════════════════════
# ⭐ STARS PAYMENTS (pre_checkout + successful)
# ═══════════════════════════════════════════

async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Telegram отправляет pre_checkout_query ПЕРЕД списанием Stars.
    Мы ОБЯЗАНЫ ответить в течение 10 секунд.
    """
    query = update.pre_checkout_query
    # Всегда подтверждаем (можно добавить проверки)
    await query.answer(ok=True)
    logger.info(f"Pre-checkout approved for user {query.from_user.id}")


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Telegram отправляет successful_payment ПОСЛЕ успешной оплаты Stars.
    Здесь мы зачисляем баланс.
    """
    payment = update.message.successful_payment
    user = update.effective_user
    payload = payment.invoice_payload  # "topup_{user_id}_{amount}_{timestamp}"

    logger.info(
        f"Successful payment from {user.id}: "
        f"payload={payload}, "
        f"charge_id={payment.telegram_payment_charge_id}"
    )

    # Парсим payload
    try:
        parts = payload.split("_")
        if len(parts) >= 3 and parts[0] == "topup":
            amount = float(parts[2])

            # Зачисляем через API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{API_BASE}/api/topup/stars/confirm",
                    json={"user_id": user.id, "amount": amount},
                    timeout=10,
                )

                if response.status_code == 200:
                    result = response.json()
                    new_balance = result.get("new_balance", "?")

                    await update.message.reply_text(
                        text=(
                            f"{EMOJI['check']} <b>Оплата прошла успешно!</b>\n"
                            f"\n"
                            f"{EMOJI['money']} Зачислено: <b>+{amount} ₽</b>\n"
                            f"{EMOJI['diamond']} Баланс: <b>{new_balance} ₽</b>\n"
                            f"\n"
                            f"{EMOJI['sparkle']} Спасибо за покупку!"
                        ),
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton(
                                text=f"{EMOJI['shop']}  В магазин",
                                web_app=WebAppInfo(url=WEBAPP_URL),
                            )],
                        ]),
                    )
                else:
                    logger.error(f"API confirm failed: {response.text}")
                    await update.message.reply_text(
                        f"{EMOJI['check']} Оплата получена! Баланс обновится в течение минуты."
                    )

    except Exception as e:
        logger.error(f"Payment processing error: {e}")
        await update.message.reply_text(
            f"{EMOJI['check']} Оплата получена! Если баланс не обновился — напишите в поддержку."
        )


# ═══════════════════════════════════════════
# 🔐 ADMIN COMMANDS
# ═══════════════════════════════════════════

async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /approve CODE — подтвердить заявку на пополнение.
    Только для админов.
    """
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    if not context.args:
        await update.message.reply_text(
            "Использование: /approve <код_заявки>"
        )
        return

    code = context.args[0].upper()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE}/api/admin/{ADMIN_PASSWORD}/approve/{code}",
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                await update.message.reply_text(
                    f"{EMOJI['check']} <b>Заявка подтверждена!</b>\n\n"
                    f"👤 User: <code>{data['user_id']}</code>\n"
                    f"💰 Сумма: <b>+{data['amount']} ₽</b>\n"
                    f"💳 Новый баланс: <b>{data['new_balance']} ₽</b>",
                    parse_mode=ParseMode.HTML,
                )
            else:
                error = response.json().get("detail", "Ошибка")
                await update.message.reply_text(f"❌ {error}")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /reject CODE [причина] — отклонить заявку.
    """
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    if not context.args:
        await update.message.reply_text(
            "Использование: /reject <код_заявки> [причина]"
        )
        return

    code = context.args[0].upper()
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Платёж не найден"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE}/api/admin/{ADMIN_PASSWORD}/reject/{code}",
                params={"reason": reason},
                timeout=10,
            )

            if response.status_code == 200:
                await update.message.reply_text(
                    f"❌ Заявка <code>{code}</code> отклонена.\n"
                    f"📝 Причина: {reason}",
                    parse_mode=ParseMode.HTML,
                )
            else:
                error = response.json().get("detail", "Ошибка")
                await update.message.reply_text(f"❌ {error}")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /pending — показать все ожидающие заявки.
    """
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE}/api/admin/{ADMIN_PASSWORD}/pending",
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                count = data["count"]

                if count == 0:
                    await update.message.reply_text(
                        f"{EMOJI['check']} Нет ожидающих заявок"
                    )
                    return

                method_names = {"ton": "💎 TON", "sbp": "🏦 СБП"}
                lines = [f"📋 <b>Ожидающие заявки ({count})</b>\n"]

                for req in data["requests"]:
                    lines.append(
                        f"\n🔑 <code>{req['request_code']}</code>\n"
                        f"   👤 ID: <code>{req['user_id']}</code>\n"
                        f"   💰 {req['amount']} ₽ • {method_names.get(req['method'], req['method'])}\n"
                        f"   → /approve {req['request_code']}"
                    )

                await update.message.reply_text(
                    "\n".join(lines),
                    parse_mode=ParseMode.HTML,
                )
            else:
                await update.message.reply_text("❌ Ошибка загрузки")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stats — общая статистика."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE}/api/admin/{ADMIN_PASSWORD}/stats",
                timeout=10,
            )

            if response.status_code == 200:
                s = response.json()
                await update.message.reply_text(
                    f"📊 <b>Статистика ЯСПЛИТ</b>\n"
                    f"\n"
                    f"👥 Пользователей: <b>{s['users_count']}</b>\n"
                    f"💳 Общий баланс: <b>{s['total_balance']} ₽</b>\n"
                    f"\n"
                    f"⏳ Ожидают проверки: <b>{s['pending_topups']}</b>\n"
                    f"✅ Подтверждено: <b>{s['approved_topups']['count']}</b> "
                    f"({s['approved_topups']['total']} ₽)\n"
                    f"⭐ Stars оплат: <b>{s['stars_payments']['count']}</b> "
                    f"({s['stars_payments']['total']} ₽)",
                    parse_mode=ParseMode.HTML,
                )

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def admin_setbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setbalance USER_ID AMOUNT — установить баланс."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Использование: /setbalance <user_id> <amount>"
        )
        return

    try:
        target_id = int(context.args[0])
        amount = context.args[1]

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE}/api/admin/{ADMIN_PASSWORD}/set_balance/{amount}/{target_id}",
                timeout=10,
            )

            if response.status_code == 200:
                await update.message.reply_text(
                    f"{EMOJI['check']} Баланс пользователя <code>{target_id}</code> "
                    f"установлен: <b>{amount} ₽</b>",
                    parse_mode=ParseMode.HTML,
                )
            else:
                await update.message.reply_text("❌ Ошибка")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


# ═══════════════════════════════════════════
# 🔄 CALLBACK HANDLERS
# ═══════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий inline-кнопок."""
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_main":
        user = query.from_user
        await query.edit_message_text(
            text=get_welcome_text(user.first_name),
            parse_mode=ParseMode.HTML,
            reply_markup=get_welcome_keyboard(),
        )


# ═══════════════════════════════════════════
# 🚀 POST-INIT: Menu Button
# ═══════════════════════════════════════════

async def post_init(application: Application):
    """Устанавливаем кнопку Menu в боте."""
    try:
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text=f"Магазин",
                web_app=WebAppInfo(url=WEBAPP_URL),
            )
        )
        logger.info("Menu button set successfully")
    except Exception as e:
        logger.warning(f"Failed to set menu button: {e}")


# ═══════════════════════════════════════════
# 🏁 MAIN
# ═══════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # ── User commands ──
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("community", community_command))
    app.add_handler(CommandHandler("support", support_command))

    # ── Stars payment handlers ──
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    app.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler)
    )

    # ── Admin commands ──
    app.add_handler(CommandHandler("approve", admin_approve))
    app.add_handler(CommandHandler("reject", admin_reject))
    app.add_handler(CommandHandler("pending", admin_pending))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("setbalance", admin_setbalance))

    # ── Callback buttons ──
    app.add_handler(CallbackQueryHandler(button_handler))

    # ── Start polling ──
    logger.info("Bot starting...")
    app.job_queue.run_repeating(keep_alive_ping, interval=600, first=10)
    logger.info("Keep-alive job scheduled every 10 minutes")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
import os
import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
    ContextTypes,
)

TOKEN = os.getenv("BOT_TOKEN")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")

PDF_URL = "https://drive.google.com/file/d/15eUb63cqzh_n68ezHcUNug4y2NPAeT7M/preview"
WORKBOOK_URL = "https://drive.google.com/file/d/1hyeYWQdy1hRlJLgum9yhoP4JPdgr0TmO/preview"
CHANNEL_URL = "https://t.me/+CbHn5jGfCaU0MjUy"

# Путь к БД берём из переменной окружения (для persistent volume на BotHost).
# Если переменная не задана — используем локальный файл рядом со скриптом.
DB_PATH = os.getenv("DATABASE_PATH", "payments.db")

logging.basicConfig(level=logging.INFO)

user_emails = {}

menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("🛒 Что входит", callback_data="product")],
    [InlineKeyboardButton("💳 Оплатить 990 ₽", callback_data="pay")]
])

back = InlineKeyboardMarkup([
    [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
])


# ---------- Работа с БД ----------

def init_db():
    """Создаёт таблицу для платежей при старте бота."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            charge_id TEXT PRIMARY KEY,
            user_id INTEGER,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    logging.info(f"БД инициализирована: {DB_PATH}")


def mark_payment_processed(charge_id: str, user_id: int, email: str = "") -> bool:
    """
    Пытается записать платёж в БД.
    True — новый платёж (обработать).
    False — дубликат (пропустить).
    """
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO payments (charge_id, user_id, email) VALUES (?, ?, ?)",
            (charge_id, user_id, email)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


# ---------- Хендлеры ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🦊 Привет. Это Лисса.\n\n"
        "Ты попал в игру, которая меняет мышление.\n\n"
        "30 дней. 10–15 целей. Один фокус.\n\n"
        "Нажми «Что входит» — расскажу подробнее.",
        reply_markup=menu
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "product":
        await query.edit_message_text(
            "🛒 Лисса.Ai: Эволюция\n\n"
            "Что входит:\n"
            "— Гайд «От глобального к локальному» (PDF)\n"
            "— Рабочая тетрадь на 30 дней (PDF)\n"
            "— Закрытый канал с ежедневной мотивацией\n\n"
            "Цена: 990 ₽ (разово)\n\n"
            "Нажми «Оплатить», чтобы получить доступ.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Оплатить 990 ₽", callback_data="pay")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
            ])
        )
        return

    if data == "back":
        await query.edit_message_text(
            "Готов начать?",
            reply_markup=menu
        )
        return

    if data == "pay":
        await query.edit_message_text(
            "📧 Перед оплатой укажи свой email для получения чека.\n\n"
            "Напиши его в чат:"
        )
        context.user_data["awaiting_email"] = True
        return


async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введённого email"""
    user_id = update.effective_user.id
    email = update.message.text.strip()

    if "@" not in email or "." not in email:
        await update.message.reply_text(
            "❌ Это не похоже на email. Попробуй снова.\n\n"
            "Напиши свой email:"
        )
        return

    user_emails[user_id] = email
    context.user_data["awaiting_email"] = False

    logging.info(f"Email сохранён: user_id={user_id}, email={email}")

    await update.message.reply_text(
        f"✅ Email сохранён: {email}\n\n"
        "Создаю счёт..."
    )

    try:
        await context.bot.send_invoice(
            chat_id=user_id,
            title="Лисса.Ai: Эволюция",
            description="Гайд + Рабочая тетрадь + Закрытый канал",
            payload="lissa_evolution_payment",
            provider_token=PROVIDER_TOKEN,
            currency="RUB",
            prices=[LabeledPrice(label="Доступ", amount=99000)],
            start_parameter="lissa_bot",
            need_email=False,
            send_email_to_provider=False,
            receipt={
                "customer": {
                    "email": email
                },
                "items": [
                    {
                        "description": "Цифровой продукт Лисса.Ai",
                        "quantity": "1.00",
                        "amount": {
                            "value": "990.00",
                            "currency": "RUB"
                        },
                        "vat_code": 1,
                        "payment_subject": "service",
                        "payment_mode": "full_payment"
                    }
                ]
            }
        )
    except Exception as e:
        await update.message.reply_text("Ошибка при создании счёта. Попробуй позже.")
        logging.error(f"Ошибка send_invoice: {e}")


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка успешного платежа с защитой от дублей через SQLite."""
    payment = update.message.successful_payment
    charge_id = payment.telegram_payment_charge_id
    user_id = update.effective_user.id
    email = user_emails.get(user_id, "")

    # Пытаемся записать платёж в БД
    try:
        is_new = mark_payment_processed(charge_id, user_id, email)
    except Exception as e:
        logging.error(f"Ошибка БД при обработке платежа: {e}")
        is_new = True  # на всякий случай выдаём материал

    if not is_new:
        logging.info(f"Дубликат платежа charge_id={charge_id}, пропускаем")
        return

    logging.info(f"Успешный платёж: charge_id={charge_id}, user_id={user_id}, email={email}")

    await update.message.reply_text(
        "✅ Оплата получена.\n\n"
        f"📘 Твой гайд: {PDF_URL}\n\n"
        f"📝 Твоя рабочая тетрадь: {WORKBOOK_URL}\n\n"
        f"📢 Ссылка на канал: {CHANNEL_URL}\n\n"
        "Заходи в канал и закрепи его.\n"
        "Твой ритм начинается сегодня."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_email"):
        await handle_email(update, context)
        return

    await update.message.reply_text("Напиши /start, чтобы начать.")


def main():
    init_db()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()

import logging
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

TOKEN = "8967181266:AAHKu1S6hLNLWmPHbpuERnsC6QJ_Xdq5iQk"
PROVIDER_TOKEN = "390540012:LIVE:102748"

PDF_URL = "https://ссылка-на-пдф"
CHANNEL_URL = "https://t.me/+CbHn5jGfCaU0MjUy"

logging.basicConfig(level=logging.INFO)

menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("🛒 Что входит", callback_data="product")],
    [InlineKeyboardButton("💳 Оплатить 990 ₽", callback_data="pay")]
])

back = InlineKeyboardMarkup([
    [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
])

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
        await query.edit_message_text("Создаю счёт...")
        try:
            await context.bot.send_invoice(
                chat_id=user_id,
                title="Лисса.Ai: Эволюция",
                description="Гайд + Рабочая тетрадь + Закрытый канал",
                payload="lissa_evolution_payment",
                provider_token=PROVIDER_TOKEN,
                currency="RUB",
                prices=[LabeledPrice(label="Доступ", amount=99000)],
                start_parameter="lissa_bot"
            )
        except Exception as e:
            await query.edit_message_text("Ошибка при создании счёта. Попробуй позже.")
            logging.error(f"Ошибка send_invoice: {e}")
        return

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Оплата получена.\n\n"
        f"📘 Твой гайд: {PDF_URL}\n\n"
        f"📢 Ссылка на канал: {CHANNEL_URL}\n\n"
        "Заходи в канал и закрепи его.\n"
        "Твой ритм начинается сегодня."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши /start, чтобы начать.")

def main():
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

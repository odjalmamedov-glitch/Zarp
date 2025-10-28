import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
import pandas as pd
import requests

# === Токен бота ===
TOKEN = "8299236175:AAErk_3tfiJoN_2sQigg5VekEyPzDcxP3qg"

# === Настройка логов ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Хранилище состояний пользователей ===
user_state = {}

# === Команда /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔹 Администратор", callback_data="admin")],
        [InlineKeyboardButton("🔹 СФУ", callback_data="sfu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите вашу должность:", reply_markup=reply_markup)

# === Обработка выбора должности ===
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id

    # Пользователь выбрал должность
    if data in ["admin", "sfu"]:
        user_state[user_id] = {"role": data}
        keyboard = [
            [InlineKeyboardButton("🔸 Настоящий месяц", callback_data=f"{data}_current")],
            [InlineKeyboardButton("🔸 Предыдущая зарплата", callback_data=f"{data}_prev")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="Выберите период:",
            reply_markup=reply_markup
        )
        return

    # Пользователь выбрал период
    if "_current" in data or "_prev" in data:
        role, period = data.split("_")
        user_state[user_id]["period"] = period
        await query.edit_message_text(
            text="Введите ваш идентификатор (пример: 11202025-12450)"
        )
        return

# === Приём текстовых сообщений ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in user_state or "period" not in user_state[user_id]:
        await update.message.reply_text("Сначала введите команду /start.")
        return

    ident = update.message.text.strip()
    user_state[user_id]["ident"] = ident

    # Пока просто подтверждаем ввод
    await update.message.reply_text(f"✅ Ваш идентификатор принят: {ident}\nДанные проверяются...")

    # Здесь позже добавим проверку с Google Таблицей
    await update.message.reply_text("⚙️ Проверка в таблице пока не подключена (тестовый режим).")

# === Основная точка входа ===
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("✅ Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()

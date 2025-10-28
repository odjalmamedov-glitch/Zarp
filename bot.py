import logging
import pandas as pd
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# === Токен Telegram ===
TOKEN = "8299236175:AAErk_3tfiJoN_2sQigg5VekEyPzDcxP3qg"

# === Настройка логов ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === ID таблицы ===
SHEET_ID = "1npQ1h6ugPMZXxrNvngAbSsw0oiH2tT4Tx0cwPWqc_aU"

# === Состояния пользователей ===
user_state = {}

# === Сопоставление листов ===
SHEET_MAP = {
    "admin": {
        "current": "Администраторы",
        "prev": "Администраторы_prev."
    },
    "sfu": {
        "current": "СФУ",
        "prev": "СФУ_prev."
    }
}

# === Получение CSV-URL ===
def get_csv_url(sheet_name):
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"

# === Команда /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔹 Администратор", callback_data="admin")],
        [InlineKeyboardButton("🔹 СФУ", callback_data="sfu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите вашу должность:", reply_markup=reply_markup)

# === Обработка выбора должности и периода ===
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data in ["admin", "sfu"]:
        user_state[user_id] = {"role": data}
        keyboard = [
            [InlineKeyboardButton("🔸 Настоящий месяц", callback_data=f"{data}_current")],
            [InlineKeyboardButton("🔸 Предыдущая зарплата", callback_data=f"{data}_prev")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите период:", reply_markup=reply_markup)
        return

    if "_current" in data or "_prev" in data:
        role, period = data.split("_")
        user_state[user_id]["period"] = period
        await query.edit_message_text("Введите ваш идентификатор (пример: 11202025-12450)")
        return

# === Проверка ID и вывод данных ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in user_state or "period" not in user_state[user_id]:
        await update.message.reply_text("Сначала введите команду /start.")
        return

    ident = update.message.text.strip()
    user_state[user_id]["ident"] = ident

    try:
        hire_date_str, tab_num_str = ident.split("-")
    except:
        await update.message.reply_text("❌ Неверный формат. Используйте пример: 11202025-12450")
        return

    # --- Получаем лист Список сотрудников ---
    staff_url = get_csv_url("Список сотрудников")
    staff_df = pd.read_csv(staff_url)

    # Ищем сотрудника по табельному номеру
    staff_row = staff_df.loc[staff_df.iloc[:, 3].astype(str) == tab_num_str]

    if staff_row.empty:
        await update.message.reply_text("❌ Табельный номер не найден в списке сотрудников.")
        return

    hire_date_from_table = str(staff_row.iloc[0, 5]).replace(".", "").replace("/", "")

    if hire_date_str != hire_date_from_table:
        await update.message.reply_text("❌ Дата приёма не совпадает с идентификатором.")
        return

    # --- Загружаем нужный лист ---
    role = user_state[user_id]["role"]
    period = user_state[user_id]["period"]
    sheet_name = SHEET_MAP[role][period]

    sheet_url = get_csv_url(sheet_name)
    df = pd.read_csv(sheet_url)

    # Ищем табельный номер в листе
    row = df.loc[df.iloc[:, 3].astype(str) == tab_num_str]

    if row.empty:
        await update.message.reply_text("❌ Не найдено данных по этому сотруднику в выбранном периоде.")
        return

    # Собираем и выводим информацию
    result_text = f"💼 Данные сотрудника ({sheet_name}):\n\n"
    for col, val in zip(df.columns[4:], row.values[0][4:]):  # пропускаем первые 4 колонки
        result_text += f"{col}: {val}\n"

    await update.message.reply_text(result_text)

# === Запуск ===
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("✅ Бот запущен и готов к работе...")
    app.run_polling()

if __name__ == "__main__":
    main()

import logging
import pandas as pd
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# 🔧 Настройки
TOKEN = "8299236175:AAErk_3tfiJoN_2sQigg5VekEyPzDcxP3qg"
SHEET_ID = "1npQ1h6ugPMZXxrNvngAbSsw0oiH2tT4Tx0cwPWqc_aU"

# Состояния пользователей
user_state = {}

# 🔹 Вспомогательные функции
def get_csv_url(sheet_name):
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"

def read_sheet(sheet_name):
    url = get_csv_url(sheet_name)
    df = pd.read_csv(url)
    return df

def parse_identifier(identifier):
    try:
        date_str, tab_number = identifier.split('-')
        return date_str, tab_number
    except Exception:
        return None, None

# 🔹 Логика команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Администратор", "СФУ"]]
    await update.message.reply_text(
        "Выберите вашу должность:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )

async def handle_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text not in ["Администратор", "СФУ"]:
        await update.message.reply_text("Выберите корректную должность.")
        return

    user_state[update.effective_chat.id] = {"position": text}
    keyboard = [["Настоящий месяц", "Предыдущая зарплата"]]
    await update.message.reply_text(
        "Выберите период:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )

async def handle_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    period = update.message.text.strip()

    if chat_id not in user_state or "position" not in user_state[chat_id]:
        await update.message.reply_text("Пожалуйста, начните заново /start")
        return

    user_state[chat_id]["period"] = period
    await update.message.reply_text("Введите ваш идентификатор (пример: 11202025-12450)")

async def handle_identifier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    identifier = update.message.text.strip()
    date_str, tab_number = parse_identifier(identifier)

    if not date_str or not tab_number:
        await update.message.reply_text("❌ Неверный формат. Пример: 11202025-12450")
        return

    info = user_state.get(chat_id, {})
    position = info.get("position")
    period = info.get("period")

    if not position or not period:
        await update.message.reply_text("❌ Начните с /start")
        return

    sheet_map = {
        ("Администратор", "Настоящий месяц"): "Администраторы",
        ("Администратор", "Предыдущая зарплата"): "Администраторы_prev.",
        ("СФУ", "Настоящий месяц"): "СФУ",
        ("СФУ", "Предыдущая зарплата"): "СФУ_prev."
    }

    sheet_name = sheet_map.get((position, period))
    if not sheet_name:
        await update.message.reply_text("❌ Ошибка выбора листа.")
        return

    try:
        df_staff = read_sheet("Список сотрудников")
        df_salary = read_sheet(sheet_name)
    except Exception as e:
        await update.message.reply_text("⚠️ Не удалось загрузить данные таблицы. Проверьте доступ.")
        logging.error(e)
        return

    # Проверяем табельный номер и дату приёма
    staff_row = df_staff[df_staff["D"].astype(str).str.strip() == tab_number]
    if staff_row.empty:
        await update.message.reply_text("❌ Табельный номер не найден в списке сотрудников.")
        return

    hire_date = staff_row.iloc[0]["F"].replace(".", "")
    if date_str != hire_date:
        await update.message.reply_text("❌ Дата приёма не совпадает.")
        return

    salary_row = df_salary[df_salary["D"].astype(str).str.strip() == tab_number]
    if salary_row.empty:
        await update.message.reply_text("❌ Зарплата не найдена в этом листе.")
        return

    # Формируем ответ
    data = salary_row.to_dict(orient="records")[0]
    text = f"✅ {position}\n📅 {period}\n\n"
    for col, val in data.items():
        text += f"{col}: {val}\n"

    await update.message.reply_text(text)

# 🔹 Основной запуск
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^(Администратор|СФУ)$"), handle_position))
    app.add_handler(MessageHandler(filters.Regex("^(Настоящий месяц|Предыдущая зарплата)$"), handle_period))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_identifier))

    print("✅ Бот запущен. Нажми Ctrl+C для остановки.")
    app.run_polling()

import os
import logging
import pandas as pd
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GSHEET_ID = os.environ.get("GSHEET_ID")  # ID таблицы (из URL) — пример: 1npQ1h6ugPMZXxrNvngAbSsw0oiH2tT4Tx0cwPWqc_aU

# states for ConversationHandler
SELECT_ROLE, SELECT_PERIOD, INPUT_ID = range(3)

role_keyboard = [["Администратор", "СФУ"]]
period_keyboard = [["Настоящий месяц", "Предыдущая зарплата"]]


def gsheet_csv_url(sheet_gid: str, gsheet_id: str = None):
    """Собирает URL вида: https://docs.google.com/spreadsheets/d/<ID>/export?format=csv&gid=<GID>"""
    if not gsheet_id:
        raise ValueError("gsheet_id required")
    return f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={sheet_gid}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выберите вашу должность:",
        reply_markup=ReplyKeyboardMarkup(role_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return SELECT_ROLE


async def select_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = update.message.text.strip()
    context.user_data['role'] = role
    await update.message.reply_text(
        "Выберите период:",
        reply_markup=ReplyKeyboardMarkup(period_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return SELECT_PERIOD


async def select_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    period = update.message.text.strip()
    context.user_data['period'] = period
    await update.message.reply_text("Введите ваш идентификатор (пример: 11202025-12450)")
    return INPUT_ID


def parse_identifier(identifier: str):
    """Разбирает идентификатор 'ДДММГГГГ-ТАБЕЛЬ' -> (date_str, tab_number)"""
    try:
        parts = identifier.split("-")
        date_part = parts[0]
        tab = parts[1]
        return date_part, tab
    except Exception:
        return None, None


def find_employee_data(gsheet_id, sheet_name, tab_number, date_hire_ddmmyyyy):
    """
    Ищем табельный номер в листе sheet_name (используем gid — ниже покажу как получить).
    Здесь упрощённо — получаем CSV по gid, затем ищем в столбце D (index 3).
    Возвращаем dict с данными (или None).
    """
    # Чтобы упростить: нам нужно знать gid листа. Ниже в инструкции как узнать gid каждого листа.
    # Предполагается, что caller знает gid для sheet_name. Для простоты — в репозитории можно хранить мапу name->gid.
    sheet_map = context_sheet_gid_map()  # определено ниже
    gid = sheet_map.get(sheet_name)
    if not gid:
        return None

    url = gsheet_csv_url(gid, gsheet_id)
    try:
        df = pd.read_csv(url)
    except Exception as e:
        logger.error("Ошибка загрузки CSV: %s", e)
        return None

    # В таблице табельный номер в столбце D -> индекс 3 (если нет заголовков — возможно будет смещение)
    # На всякий случай приведём к строке:
    df['tab_str'] = df.iloc[:, 3].astype(str).str.strip()
    found = df[df['tab_str'] == str(tab_number)]
    if found.empty:
        return None

    # Найдём на листе "Список сотрудников" дату приёма для Tab
    # загрузим лист "Список сотрудников" (gid указан в map)
    gid_list = sheet_map.get("Список сотрудников")
    if not gid_list:
        return None
    url_list = gsheet_csv_url(gid_list, gsheet_id)
    df_list = pd.read_csv(url_list)
    df_list['tab_str'] = df_list.iloc[:, 3].astype(str).str.strip()  # столбец D
    found_list = df_list[df_list['tab_str'] == str(tab_number)]
    if found_list.empty:
        return None

    # дата приёма в листе Список сотрудников — столбец F -> индекс 5
    date_hire = str(found_list.iloc[0, 5]).strip()  # ожидаем формат ДД.MM.ГГГГ
    if date_hire != date_hire_ddmmyyyy:
        return None

    # Возвращаем первую найденную строку с зарплатными данными как словарь
    row = found.iloc[0]
    return row.to_dict()


def context_sheet_gid_map():
    """
    Здесь укажи мапу: имя листа -> gid листа (из URL Google Sheets).
    Пример:
    {
      "Администраторы": 1964214162,
      "Администраторы_prev.": 1795966741,
      "СФУ": 0,
      "СФУ_prev.": 1802502204,
      "Список сотрудников": 1457379633
    }
    """
    return {
        # <-- ЗАПОЛНИ ЗДЕСЬ реальные gid из твоей таблицы!
        "Администраторы": 1964214162,
        "Администраторы_prev.": 1795966741,
        "СФУ": 0,
        "СФУ_prev.": 1802502204,
        "Список сотрудников": 1457379633
    }


async def input_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identifier = update.message.text.strip()
    date_part, tab = parse_identifier(identifier)
    if not date_part or not tab:
        await update.message.reply_text("❌ Неверный формат идентификатора. Пример: 11202025-12450")
        return ConversationHandler.END

    role = context.user_data.get('role')
    period = context.user_data.get('period')
    # соответствие листов:
    if role == "Администратор":
        sheet_name = "Администраторы" if period == "Настоящий месяц" else "Администраторы_prev."
    else:
        sheet_name = "СФУ" if period == "Настоящий месяц" else "СФУ_prev."

    gsheet_id = os.environ.get("GSHEET_ID")
    result = find_employee_data(gsheet_id, sheet_name, tab, date_part)
    if not result:
        await update.message.reply_text("❌ Идентификатор не найден. Проверьте правильность данных.")
        return ConversationHandler.END

    # Формируем вывод (упрощённо — выводим всю строку)
    text_lines = [f"Результат для табельного номера {tab} ({role}, {period}):"]
    for k, v in result.items():
        text_lines.append(f"{k}: {v}")
    await update.message.reply_text("\n".join(text_lines))
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not set")
        exit(1)

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECT_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_role)],
            SELECT_PERIOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_period)],
            INPUT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_id)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(conv_handler)
    logger.info("Bot started (polling)...")
    app.run_polling()

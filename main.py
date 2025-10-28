#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простой скрипт для чтения публичной Google Таблицы (по ID) и вывода
данных по сотруднику (Администратор или СФУ) по идентификатору ДДММГГГГ-ЧЧЧЧ.

Работает без credentials — использует публичный CSV-экспорт Google Sheets.
"""

import sys
import re
import csv
import requests
from datetime import datetime
from urllib.parse import quote_plus

# -----------------------
# настройки (редактируй только эти переменные при необходимости)
SPREADSHEET_ID = "1npQ1h6ugPMZXxrNvngAbSsw0oiH2tT4Tx0cwPWqc_aU"

ADMIN_SHEET = "Администраторы"
SFU_SHEET = "СФУ"
ADMIN_PREV_SHEET = "Администраторы_prev."
SFU_PREV_SHEET = "СФУ_prev."
EMPLOYEE_LIST_SHEET = "Список сотрудников"
# -----------------------

ADMIN_COLUMNS = [
    "Кол-во сим-карт", "Бонус за UCELL", "Кол-во лимитов с коэффом", "План по лимитам",
    "Выполнение плана по лимитам", "Бонус за лимиты", "Кол-во банковских карт",
    "План по банковским картам", "Выполнение плана по банковским картам",
    "Бонус за банковским картам", "SLA приёмки", "Понижающий коэффициент SLA",
    "Ошибочное оформление возвратов", "Понижающий коэффициент возвратов",
    "Результат ВЧЛ", "ВЧЛ", "Бонус за ВЧЛ", "Стабильность",
    "Общая сумма бонуса", "Бонус + доп. начисления на руки",
    "Гросс итог бонуса", "Бонус + доп. начисления в гроссе"
]

SFU_COLUMNS = [
    "Кол-во сим-карт", "План UCELL", "Выполнение плана по UCELL", "Бонус за UCELL",
    "Банковские карты факт", "План по банковским картам", "Выполнение плана по банковским картам",
    "Бонус за банковские карты", "Банковские карты", "Ошибочные оформления бк",
    "Результат ВЧЛ", "ВЧЛ", "Бонус за ВЧЛ", "Общая сумма бонуса",
    "Бонус + доп. начисления на руки", "Гросс итог бонуса", "Бонус + доп. начисления в гроссе"
]


# -----------------------
# Вспомогательные функции
# -----------------------
def fetch_sheet_as_rows(sheet_name):
    """
    Загружает лист по имени как CSV и возвращает список строк (каждая строка — список ячеек).
    Требует, чтобы таблица была публична (просмотр по ссылке).
    """
    safe_name = quote_plus(sheet_name)
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={safe_name}"
    try:
        resp = requests.get(url, timeout=15)
    except Exception as e:
        raise RuntimeError(f"Ошибка запроса к Google Sheets: {e}")
    if resp.status_code != 200:
        raise RuntimeError(f"Не удалось скачать лист '{sheet_name}'. HTTP {resp.status_code}")
    # Устанавливаем корректную кодировку, если сервер её не указал
    resp.encoding = resp.apparent_encoding or "utf-8"
    text = resp.text
    reader = csv.reader(text.splitlines())
    rows = [row for row in reader]
    return rows


def normalize_date_value(value):
    """Приводит значение даты к формату DD.MM.YYYY для сравнения."""
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    # Если уже в формате с точками или дефисами/слешами — заменим на точки
    s = s.replace("/", ".").replace("-", ".")
    # Если это похоже на Excel-число (кома или точка) — попробуем распарсить через datetime
    patterns = ["%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%d/%m/%Y"]
    for p in patterns:
        try:
            dt = datetime.strptime(s, p)
            return dt.strftime("%d.%m.%Y")
        except Exception:
            continue
    # Попытка найти числа в строке: 8-10 цифр подряд -> распарсим как DDMMYYYY
    m = re.search(r"(\d{2})(\d{2})(\d{4})", s)
    if m:
        return f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
    return s


def validate_identifier_and_lookup(identifier):
    """
    Проверяет идентификатор формата DDMMYYYY-NNNN и сверяет
    табельный номер и дату найма со 'Список сотрудников' (колонки D и F).
    Возвращает (is_valid_bool, personnel_number, hire_date) .
    """
    m = re.match(r"^(\d{2})(\d{2})(\d{4})-(\d{4,5})$", identifier)
    if not m:
        return False, None, None
    dd, mm, yyyy, personnel = m.groups()
    hire_date = f"{dd}.{mm}.{yyyy}"

    # Попытка загрузить лист "Список сотрудников"
    try:
        rows = fetch_sheet_as_rows(EMPLOYEE_LIST_SHEET)
    except Exception as e:
        # Если не получилось загрузить — считаем идентификатор не прошедшим верификацию
        # но возвращаем форматированные значения для диагностики.
        print(f"⚠️ Не удалось проверить 'Список сотрудников': {e}")
        return False, personnel, hire_date

    # Ожидаем, что есть заголовок в первой строке. Проверяем строки, начиная со второй.
    for idx, row in enumerate(rows[1:], start=2):
        # Колонка D -> индекс 3, колонка F -> индекс 5
        sheet_personnel = ""
        sheet_hire = ""
        try:
            sheet_personnel = str(row[3]).strip()
        except Exception:
            sheet_personnel = ""
        try:
            sheet_hire = normalize_date_value(row[5])
        except Exception:
            sheet_hire = normalize_date_value(row[5] if len(row) > 5 else "")
        if sheet_personnel.replace(" ", "") == personnel.replace(" ", "") and sheet_hire == hire_date:
            return True, personnel, hire_date
    return False, personnel, hire_date


def get_sheet_name(role, month):
    if role == "Администратор":
        return ADMIN_SHEET if month == "Настоящий месяц" else ADMIN_PREV_SHEET
    else:
        return SFU_SHEET if month == "Настоящий месяц" else SFU_PREV_SHEET


def process_user_input(role, month, identifier):
    started = datetime.now()
    print(f"Запуск обработки: {role}, {month}, {identifier}")

    if role not in ["Администратор", "СФУ"]:
        return "❌ Ошибка: неверная роль. Укажите 'Администратор' или 'СФУ'."

    if month not in ["Настоящий месяц", "Предыдущая зарплата"]:
        return "❌ Ошибка: неверный месяц. Выберите 'Настоящий месяц' или 'Предыдущая зарплата'."

    is_valid, personnel_number, hire_date = validate_identifier_and_lookup(identifier)
    if not is_valid:
        return ("❌ Ошибка: неверный идентификатор или не найден в 'Список сотрудников'. "
                "Формат должен быть ДДММГГГГ-ЧЧЧЧ (например: 13102025-9224).")

    sheet_name = get_sheet_name(role, month)
    # загружаем лист как CSV
    try:
        rows = fetch_sheet_as_rows(sheet_name)
    except Exception as e:
        return f"❌ Ошибка при загрузке листа '{sheet_name}': {e}"

    if len(rows) < 2:
        return f"❌ Лист '{sheet_name}' не содержит необходимой структуры (ожидается заголовок на второй строке)."

    headers = rows[1]  # согласно твоему сценарию заголовки на второй строке
    # на всякий случай убираем лишние пробелы в заголовках
    headers = [h.strip() for h in headers]

    if "Табельный номер" not in headers:
        return "❌ Ошибка: столбец 'Табельный номер' не найден в заголовках."

    personnel_idx = headers.index("Табельный номер")

    target_row = None
    for row in rows[2:]:
        # если строка короче — пропускаем
        if personnel_idx >= len(row):
            continue
        cell = str(row[personnel_idx]).replace(" ", "")
        if cell == personnel_number:
            target_row = row
            break

    if not target_row:
        return f"❌ Данные для табельного номера {personnel_number} не найдены на листе '{sheet_name}'."

    columns = ADMIN_COLUMNS if role == "Администратор" else SFU_COLUMNS
    lines = [
        f"📋 Данные для {role} (Табельный номер: {personnel_number}, Месяц: {month})",
        f"Дата найма: {hire_date}",
        ""
    ]

    for col in columns:
        if col in headers:
            idx = headers.index(col)
            val = ""
            if idx < len(target_row):
                val = target_row[idx].strip()
            lines.append(f"{col}: {val or '0'}")
        else:
            # подсказываем в лог, но не ломаем вывод
            print(f"⚠️ Внимание: столбец '{col}' не найден в '{sheet_name}' (пропускаю).")

    elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
    lines.append("")
    lines.append(f"Время выполнения: {elapsed_ms} мс")

    return "\n".join(lines)


# -----------------------
# Точка входа — CLI
# -----------------------
def print_usage_and_exit():
    print("Использование:")
    print("  python3 main.py [Роль] [Месяц] [Идентификатор]")
    print("Пример:")
    print("  python3 main.py Администратор \"Настоящий месяц\" 13102025-9224")
    print("Если аргументы не переданы — используется тестовый пример.")
    sys.exit(0)


if __name__ == "__main__":
    # Аргументы: role, month, identifier
    if len(sys.argv) == 4:
        role_arg = sys.argv[1]
        month_arg = sys.argv[2]
        id_arg = sys.argv[3]
    elif len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        print_usage_and_exit()
    else:
        # дефолтные тестовые значения (замени при необходимости)
        role_arg = "Администратор"
        month_arg = "Настоящий месяц"
        id_arg = "13102025-9224"

    try:
        out = process_user_input(role_arg, month_arg, id_arg)
        print("\n--- РЕЗУЛЬТАТ ---\n")
        print(out)
    except Exception as exc:
        print(f"НЕОЖИДАННАЯ ОШИБКА: {exc}")
        sys.exit(1)

import gspread
from datetime import datetime

# === НАСТРОЙКИ ===
SPREADSHEET_URL = 'https://docs.google.com/spreadsheets/d/1npQ1h6ugPMZXxrNvngAbSsw0oiH2tT4Tx0cwPWqc_aU'

ADMIN_SHEET = 'Администраторы'
SFU_SHEET = 'СФУ'
ADMIN_PREV_SHEET = 'Администраторы_prev.'
SFU_PREV_SHEET = 'СФУ_prev.'
EMPLOYEE_LIST_SHEET = 'Список сотрудников'

ADMIN_COLUMNS = [
    'Кол-во сим-карт', 'Бонус за UCELL', 'Кол-во лимитов с коэффом', 'План по лимитам',
    'Выполнение плана по лимитам', 'Бонус за лимиты', 'Кол-во банковских карт',
    'План по банковским картам', 'Выполнение плана по банковским картам',
    'Бонус за банковским картам', 'SLA приёмки', 'Понижающий коэффициент SLA',
    'Ошибочное оформление возвратов', 'Понижающий коэффициент возвратов',
    'Результат ВЧЛ', 'ВЧЛ', 'Бонус за ВЧЛ', 'Стабильность',
    'Общая сумма бонуса', 'Бонус + доп. начисления на руки',
    'Гросс итог бонуса', 'Бонус + доп. начисления в гроссе'
]

SFU_COLUMNS = [
    'Кол-во сим-карт', 'План UCELL', 'Выполнение плана по UCELL', 'Бонус за UCELL',
    'Банковские карты факт', 'План по банковским картам', 'Выполнение плана по банковским картам',
    'Бонус за банковские карты', 'Банковские карты', 'Ошибочные оформления бк',
    'Результат ВЧЛ', 'ВЧЛ', 'Бонус за ВЧЛ', 'Общая сумма бонуса',
    'Бонус + доп. начисления на руки', 'Гросс итог бонуса', 'Бонус + доп. начисления в гроссе'
]

# === ФУНКЦИИ ===
def get_public_client():
    """Подключение к публичной таблице (без credentials)"""
    return gspread.public()

def open_sheet(sheet_name):
    client = get_public_client()
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    return spreadsheet.worksheet(sheet_name)

def normalize_date(date):
    if not date:
        return ''
    if isinstance(date, datetime):
        return date.strftime('%d.%m.%Y')
    return str(date).replace('/', '.').replace('-', '.').strip()

def validate_identifier(identifier):
    import re
    match = re.match(r'^(\d{2})(\d{2})(\d{4})-(\d{4,5})$', identifier)
    if not match:
        return False, None, None
    day, month, year, personnel_number = match.groups()
    hire_date = f'{day}.{month}.{year}'
    return True, personnel_number, hire_date

def get_sheet_name(role, month):
    if role == 'Администратор':
        return ADMIN_SHEET if month == 'Настоящий месяц' else ADMIN_PREV_SHEET
    else:
        return SFU_SHEET if month == 'Настоящий месяц' else SFU_PREV_SHEET

def process_user_input(role, month, identifier):
    start_time = datetime.now()
    print(f'Запуск обработки: {role}, {month}, {identifier}')

    if role not in ['Администратор', 'СФУ']:
        return '❌ Ошибка: неверная роль. Укажите "Администратор" или "СФУ".'

    if month not in ['Настоящий месяц', 'Предыдущая зарплата']:
        return '❌ Ошибка: неверный месяц.'

    is_valid, personnel_number, hire_date = validate_identifier(identifier)
    if not is_valid:
        return '❌ Ошибка: неверный идентификатор (формат ДДММГГГГ-ЧЧЧЧ).'

    sheet_name = get_sheet_name(role, month)
    sheet = open_sheet(sheet_name)
    data = sheet.get_all_values()

    headers = data[1]
    try:
        personnel_idx = headers.index('Табельный номер')
    except ValueError:
        return '❌ Ошибка: столбец "Табельный номер" не найден.'

    # Поиск строки по табельному номеру
    target_row = None
    for row in data[2:]:
        if str(row[personnel_idx]).replace(' ', '') == personnel_number:
            target_row = row
            break

    if not target_row:
        return f'❌ Данные для табельного номера {personnel_number} не найдены.'

    columns = ADMIN_COLUMNS if role == 'Администратор' else SFU_COLUMNS
    result_lines = [
        f'📋 Данные для {role} (Табельный номер: {personnel_number}, Месяц: {month})',
        f'Дата найма: {hire_date}',
        ''
    ]
    for col in columns:
        if col in headers:
            idx = headers.index(col)
            value = target_row[idx] if idx < len(target_row) else ''
            result_lines.append(f'{col}: {value or "0"}')

    elapsed = (datetime.now() - start_time).total_seconds() * 1000
    print(f'✅ Готово за {elapsed:.0f} мс')
    return '\n'.join(result_lines)

if __name__ == '__main__':
    role = 'Администратор'
    month = 'Настоящий месяц'
    identifier = '13102025-9224'
    print(process_user_input(role, month, identifier))

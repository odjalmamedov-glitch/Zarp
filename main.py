import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# === НАСТРОЙКИ ===
SPREADSHEET_ID = '1npQ1h6ugPMZXxrNvngAbSsw0oiH2tT4Tx0cwPWqc_aU'

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
def get_service():
    """Авторизация через Google Service Account"""
    scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
    client = gspread.authorize(creds)
    return client


def normalize_date(date_value):
    """Приводим даты к формату ДД.ММ.ГГГГ"""
    if not date_value:
        return ''
    if isinstance(date_value, str):
        return date_value.strip().replace('/', '.').replace('-', '.')
    if isinstance(date_value, datetime):
        return date_value.strftime('%d.%m.%Y')
    return str(date_value)


def validate_identifier(client, identifier):
    """Проверяем идентификатор вида ДДММГГГГ-ЧЧЧЧ"""
    print(f'Проверка идентификатора: {identifier}')
    import re
    match = re.match(r'^(\d{2})(\d{2})(\d{4})-(\d{4,5})$', identifier)
    if not match:
        return False, None, None

    day, month, year, personnel_number = match.groups()
    hire_date = f'{day}.{month}.{year}'

    # Проверяем в листе "Список сотрудников"
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(EMPLOYEE_LIST_SHEET)
    data = sheet.get_all_values()[1:]  # пропускаем заголовок
    for row in data:
        try:
            sheet_number = str(row[3]).strip()  # столбец D
            sheet_date = normalize_date(row[5])  # столбец F
            if sheet_number == personnel_number and sheet_date == hire_date:
                return True, personnel_number, hire_date
        except IndexError:
            continue
    return False, None, None


def get_sheet_name(role, month):
    if role == 'Администратор':
        return ADMIN_SHEET if month == 'Настоящий месяц' else ADMIN_PREV_SHEET
    else:
        return SFU_SHEET if month == 'Настоящий месяц' else SFU_PREV_SHEET


def process_user_input(role, month, identifier):
    start_time = datetime.now()
    print(f'Запуск обработки: {role}, {month}, {identifier}')

    if role not in ['Администратор', 'СФУ']:
        return f'❌ Ошибка: неверная роль. Укажите "Администратор" или "СФУ".'

    if month not in ['Настоящий месяц', 'Предыдущая зарплата']:
        return f'❌ Ошибка: неверный месяц.'

    client = get_service()

    is_valid, personnel_number, hire_date = validate_identifier(client, identifier)
    if not is_valid:
        return f'❌ Ошибка: неверный идентификатор (формат ДДММГГГГ-ЧЧЧЧ).'

    sheet_name = get_sheet_name(role, month)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(sheet_name)
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
        else:
            print(f'⚠️ Столбец "{col}" не найден')

    elapsed = (datetime.now() - start_time).total_seconds() * 1000
    print(f'✅ Готово за {elapsed:.0f} мс')
    return '\n'.join(result_lines)


if __name__ == '__main__':
    # 🔧 Тестовый пример
    role = 'Администратор'
    month = 'Настоящий месяц'
    identifier = '13102025-9224'  # формат ДДММГГГГ-ЧЧЧЧ

    result = process_user_input(role, month, identifier)
    print('\n=== РЕЗУЛЬТАТ ===')
    print(result)

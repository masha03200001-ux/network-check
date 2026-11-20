import os
import json
import subprocess
import subprocess
import socket
import concurrent.futures
from datetime import datetime, timezone, timedelta
import gspread
def ping_ip(ip):
    ip = str(ip).strip()
    if not ip:
        return ""
    
    # Способ 1: Обычный пинг (3 пакета с ожиданием до 5 секунд)
    try:
        subprocess.check_output(
            ["ping", "-c", "3", "-W", "5", ip],
            stderr=subprocess.STDOUT
        )
        return "Онлайн"
    except Exception:
        pass

    # Способ 2: Если пинг заблокирован провайдером, проверяем популярные порты (веб и MikroTik)
    for port in (80, 443, 8291, 22):
        try:
            with socket.create_connection((ip, port), timeout=3):
                return "Онлайн"
        except Exception:
            continue

    return "Офлайн"

def main():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    sheet_id = os.environ.get("SHEET_ID")
    
    if not creds_json or not sheet_id:
        print("Ошибка: не найдены секретные ключи.")
        return

    # Авторизация в Google Таблицах
    creds_dict = json.loads(creds_json)
    client = gspread.service_account_from_dict(creds_dict)

    spreadsheet = client.open_by_key(sheet_id)
    main_sheet = spreadsheet.worksheet("Мониторинг")

    # Читаем все строки с листа Мониторинг (столбец A = индекс 0, столбец D = индекс 3)
    all_rows = main_sheet.get_all_values()
    if len(all_rows) < 2:
        print("Список адресов пуст.")
        return

    targets = []
    for row in all_rows[1:]:
        ip = str(row).strip() if len(row) > 0 else ""
        if not ip:
            continue
        # Берем название города из столбца D (четвертая колонка, индекс 3)
        raw_name = str(row).strip() if len(row) > 3 else ""
        name = raw_name.capitalize() if raw_name else ip

        # Убираем запрещенные для названий вкладок символы
        for bad_char in ['[', ']', '*', '/', '\\', '?', ':']:
            name = name.replace(bad_char, '-')
        targets.append((ip, name))

    ips = [t for t in targets]

    # Пингуем все IP параллельно
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        ping_results = list(executor.map(ping_ip, ips))

    # Текущее время (Киев, UTC+2)
    tz = timezone(timedelta(hours=2))
    now_str = datetime.now(tz).strftime("%d.%m.%Y %H:%M:%S")

    # Получаем список уже существующих вкладок в таблице (приводим к нижнему регистру для надежного поиска)
    existing_sheets = {ws.title.strip().lower(): ws for ws in spreadsheet.worksheets()}

    # Записываем результат для каждого города в его вкладку
    for (ip, name), status in zip(targets, ping_results):
        lookup_key = name.strip().lower()
        if lookup_key in existing_sheets:
            target_sheet = existing_sheets[lookup_key]
        else:
            target_sheet = spreadsheet.add_worksheet(title=name, rows=1000, cols=5)
            target_sheet.append_row(["Дата и время", "Статус", "IP-адрес"])

        # Добавляем новую строчку с результатом
        target_sheet.append_row([now_str, status, ip])

    print(f"Проверка успешно завершена. Обновлено вкладок: {len(targets)}")

if __name__ == "__main__":
    main()

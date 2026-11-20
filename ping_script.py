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

    # Читаем все строки: первая колонка (A) — IP, вторая колонка (B) — Город
    all_rows = main_sheet.get_all_values()
    targets = []

    for row in all_rows[1:]:
        if len(row) < 2:
            continue

        ip = str(row.pop(0)).strip()
        raw_city = str(row.pop(0)).strip()

        if not ip or not raw_city:
            continue

        # Оставляем в названии только буквы, пробелы и дефисы, первую букву делаем заглавной
        city_name = "".join(ch for ch in raw_city if ch.isalpha() or ch in (" ", "-")).strip().capitalize()

        if city_name:
            targets.append((ip, city_name))

    print(f"Найдено городов во второй колонке: {len(targets)}")
    if not targets:
        return

    ips = [ip for ip, _ in targets]

    # Пингуем все IP параллельно
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        ping_results = list(executor.map(ping_ip, ips))

    # Текущее время (Киев, UTC+2)
    tz = timezone(timedelta(hours=2))
    now_str = datetime.now(tz).strftime("%d.%m.%Y %H:%M:%S")

    # Получаем список уже существующих вкладок
    existing_sheets = {ws.title.strip().lower(): ws for ws in spreadsheet.worksheets()}

    for (ip, city_name), status in zip(targets, ping_results):
        lookup_key = city_name.strip().lower()
        if lookup_key in existing_sheets:
            target_sheet = existing_sheets[lookup_key]
        else:
            print(f"Создаю вкладку: {city_name}")
            target_sheet = spreadsheet.add_worksheet(title=city_name, rows=1000, cols=5)
            target_sheet.append_row(["Дата и время", "Статус"])

        # Записываем дату/время и статус
        target_sheet.append_row([now_str, status])

    print(f"Проверка завершена. Обновлено вкладок: {len(targets)}")

if __name__ == "__main__":
    main()

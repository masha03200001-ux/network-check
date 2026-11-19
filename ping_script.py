import os
import json
import subprocess
import concurrent.futures
from datetime import datetime, timezone, timedelta
import gspread
from google.oauth2.service_account import Credentials

def ping_ip(ip):
    ip = str(ip).strip()
    if not ip:
        return ("", "")
    
    # Пингуем: 1 пакет, таймаут 2 секунды (для Linux серверов GitHub)
    try:
        output = subprocess.check_output(
            ["ping", "-c", "1", "-W", "2", ip],
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        # Извлекаем время задержки (time=XX.X ms)
        latency = "ОК"
        for part in output.split():
            if part.startswith("time="):
                latency = part.replace("time=", "")
                break
        return ("Онлайн", latency)
    except subprocess.CalledProcessError:
        return ("Офлайн", "-")
    except Exception:
        return ("Ошибка проверки", "-")

def main():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    sheet_id = os.environ.get("SHEET_ID")
    
    if not creds_json or not sheet_id:
        print("Ошибка: не найдены секретные ключи.")
        return

    # Авторизация в Google Таблицах
    creds_dict = json.loads(creds_json)
    scopes = ["https://googleapis.com"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(sheet_id).worksheet("Мониторинг")
    
    # Читаем IP из столбца A (начиная со 2-й строки)
    all_values = sheet.col_values(1)
    if len(all_values) < 2:
        print("Список адресов пуст.")
        return
        
    ips = all_values[1:]
    
    # Пингуем все IP параллельно для максимальной скорости
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        ping_results = list(executor.map(ping_ip, ips))

    # Текущее время (Киев, UTC+2 / UTC+3 в зависимости от сезона)
    tz = timezone(timedelta(hours=2))
    now_str = datetime.now(tz).strftime("%d.%m.%Y %H:%M:%S")

    # Формируем данные для записи в столбцы B, C, D
    rows_to_update = []
    for status, latency in ping_results:
        if status == "":
            rows_to_update.append(["", "", ""])
        else:
            rows_to_update.append([status, latency, now_str])

    # Записываем результат в таблицу одним запросом
    end_row = len(rows_to_update) + 1
    sheet.update(range_name=f"B2:D{end_row}", values=rows_to_update)
    print(f"Проверка успешно завершена. Обработано записей: {len(rows_to_update)}")

if __name__ == "__main__":
    main()

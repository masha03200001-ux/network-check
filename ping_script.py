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

    # Читаем IP из столбца A главного листа (начиная со 2-й строки)
    all_values = main_sheet.col_values(1)
    if len(all_values) < 2:
        print("Список адресов пуст.")
        return

    # Очищаем список от пустых строк
    ips = [str(ip).strip() for ip in all_values[1:] if str(ip).strip()]

    # Пингуем все IP параллельно
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        ping_results = list(executor.map(ping_ip, ips))

    # Текущее время (Киев, UTC+2)
    tz = timezone(timedelta(hours=2))
    now_str = datetime.now(tz).strftime("%d.%m.%Y %H:%M:%S")

    # Получаем список уже существующих вкладок в таблице
    existing_sheets = {ws.title: ws for ws in spreadsheet.worksheets()}

    # Записываем результат для каждого IP в его личную вкладку новой строкой
    for ip, status in zip(ips, ping_results):
        if ip in existing_sheets:
            ip_sheet = existing_sheets[ip]
        else:
            # Если вкладки для этого IP ещё нет — создаём её и добавляем шапку
            ip_sheet = spreadsheet.add_worksheet(title=ip, rows=1000, cols=5)
            ip_sheet.append_row(["Дата и время", "Статус"])

        # Добавляем новую строчку с результатом в конец вкладки
        ip_sheet.append_row([now_str, status])

    print(f"Проверка успешно завершена. Обновлено вкладок: {len(ips)}")

if __name__ == "__main__":
    main()

# modules/kv_generator.py
import os
import fnmatch

MODULE_INFO = {
    "name": "KV Generator: Connection Test",
    "group": "KV Generator",
    "pattern": "SedecalSerial.log*"
}

def analyze(files, start_date, end_date):
    """
    Фильтруем файлы по шаблону и считаем их количество.
    (При необходимости можно добавить фильтрацию по диапазону дат.)
    """
    relevant_files = []
    for file in files:
        if fnmatch.fnmatch(os.path.basename(file), MODULE_INFO["pattern"]):
            relevant_files.append(file)
    count = len(relevant_files)
    if count > 0:
        status = "Green"
        result = f"Найдено {count} файлов."
    else:
        status = "Red"
        result = "Файлы не найдены."
    return result, status

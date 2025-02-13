import os
import fnmatch
from datetime import datetime

MODULE_INFO = {
    "name": "XVI panel: pots",
    "group": "XVI panels",
    "pattern": "KVPanel*.log",
    "version": "0.4"
}

# Determine the log file path (one level up)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.join(current_dir, "..")
log_file = os.path.join(parent_dir, "output.log")

def analyze(files, start_date, end_date):
    #print("files>: ",files)
    """
    Filter files by the specified pattern and count them.
    """
    relevant_files = []
    for file in files:
        if fnmatch.fnmatch(os.path.basename(file), MODULE_INFO["pattern"]):
            relevant_files.append(file)
    count = len(relevant_files)
    if count > 0:
        status = "Green"
        result = f"Found {count} files."
    else:
        status = "Red"
        result = "Files not found."

    # Format the start date (if it's a date object, convert it to a string)
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Log the information to the file (the file is created if it doesn't exist)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"=== {MODULE_INFO['name']} | Start: {start_time} |\n {result}\n")

    return result, status
# NOTE: All comments and messages in the code must be in US English only. No other languages are permitted.
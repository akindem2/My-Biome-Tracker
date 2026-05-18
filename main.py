import customtkinter as ctk

import requests

import os
import json
from pathlib import Path

import threading

import time
from datetime import datetime, timezone
app = ctk.CTk()
app.geometry("800x250")
app.title("Biome Scanner")

tabview = ctk.CTkTabview(app)
tabview.pack(fill="both", expand=True, padx=20, pady=20)

tab1 = tabview.add("Home")
tab2 = tabview.add("Settings")
tab3 = tabview.add("Biomes")
tab4 = tabview.add("Merchants")

role_ids = {}

scroll3 = ctk.CTkScrollableFrame(tab3)
scroll3.pack(fill="both", expand=True)

app_dir = os.path.join(os.getenv("LOCALAPPDATA"), "My Biome Scanner")
os.makedirs(app_dir, exist_ok=True)
file_path = os.path.join(app_dir, "settings.json")

localappdata = os.getenv("LOCALAPPDATA")

biomes_url = "https://raw.githubusercontent.com/akindem2/My-Biome-Tracker/refs/heads/main/biomes.json"



assigned_log = None

size = 0

last_read_line = 0

current_biome = ""

scanning = False
#------------------------
#--BUTTON FUNCTIONS
#------------------------

def toggle():
    global scanning
    if toggle_button.cget("text") == "Start":
        toggle_button.configure(text = "Stop", fg_color = "#FF0000", hover_color = "#ff6161")
        identify_log()
        scanning = True
        thread = threading.Thread(target=scanner_loop, daemon=True)
        thread.start()
        send_start_message()
    else:
        toggle_button.configure(text = "Start", fg_color = "#009C00", hover_color = "#016e01")
        scanning = False
        send_stop_message()

def save_settings():
    # Extract role IDs from entry widgets
    role_ids.clear()
    for biome in biomes:
        title = biome["title"]
        role_ids[title] = role_entries[title].get()

    settings = {
        "webhook url": webhook_entry.get(),
        "ps link": ps_entry.get(),
        "user id": user_entry.get(),
        "role ids": role_ids
    }

    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(settings, json_file, indent=4)

    print(f"Settings saved to {file_path}")


def test_message():
    url = webhook_entry.get()
    data = {
        "embeds": [  # Note the start of the list
            {
                "title": "Test Message",
                "description": "Test message for Jane Juliet",
                "color": 0x00FF00,
                "fields": [
                    {
                        "name": "Time",
                        "value": f"<t:{int(time.time())}:T>, <t:{int(time.time())}:R>"
                    }
                ],
                "footer": {
                    "text": "My Biome Scanner"
                }
            }
        ]
    }
    requests.post(url, json = data)



#------------------------
#--WEBHOOK FUNCTIONS
#------------------------

def send_start_message():
    url = webhook_entry.get()
    data = {
        "embeds": [
            {
                "title": "Macro Started",
                "description": "My Biome Tracker has started!",
                "color": 0x00FF00,
                "fields": [
                    {
                        "name": "Username",
                        "value": userid_to_username(user_entry.get()),
                    },
                    {
                        "name": "Time",
                        "value": f"<t:{int(time.time())}:T>, <t:{int(time.time())}:R>"
                    }
                ],
                "footer": {
                    "text": "My Biome Scanner"
                }
            }
        ]
    }
    result = requests.post(url, json = data)

    if result.status_code == 204: print("Message Sent!")
    else: print(f"Failed: {result.status_code}, {result.text}")

def send_stop_message():
    url = webhook_entry.get()
    data = {
        "embeds": [
            {
                "title": "Macro Stopped",
                "description": "My Biome Tracker has stopped!",
                "color": 0xFF0000,
                "fields": [
                    {
                        "name": "Time",
                        "value": f"<t:{int(time.time())}:T>, <t:{int(time.time())}:R>"
                    }
                ],
                "footer": {
                    "text": "My Biome Scanner"
                }
            }
        ]
    }
    result = requests.post(url, json = data)

    if result.status_code == 204: print("Message Sent!")
    else: print(f"Failed: {result.status_code}, {result.text}")

def send_biome_start(biome_title):
    for biome in biomes:
        if biome_title == biome["title"]:
            content = ""
            if role_entries[biome["title"]].get():
                content = f"<@&{role_entries[biome["title"]].get()}>"
            url = webhook_entry.get()
            if biome['everyone'] == True:
                content = "@everyone"
            data = {
                "content":content,
                "embeds": [
                    {
                        "title": f"{biome['title']} Biome Started",
                        "color": int(biome['color'], 16),
                        "thumbnail": {
                            "url": biome['thumbnail']
                            },
                        "fields": [
                            {
                                "name": "Username",
                                "value": userid_to_username(user_entry.get()),
                            },
                            {
                                "name": "PS Link",
                                "value": ps_entry.get()
                            },
                            {
                                "name": "Time",
                                "value": f"<t:{int(time.time())}:T>, <t:{int(time.time())}:R>"
                            }
                        ],
                        "footer": {
                            "text": "My Biome Scanner"
                        }
                    }
                ]
            }
            result = requests.post(url, json = data)

            if result.status_code == 204: print("Message Sent!")
            else: print(f"Failed: {result.status_code}, {result.text}")

def send_biome_stop(biome_title):
    for biome in biomes:
        if biome_title == biome["title"]:
            url = webhook_entry.get()
            data = {
                "embeds": [
                    {
                        "title": f"{biome['title']} BIOME ENDED",
                        "color": int(biome['color'], 16),
                        "thumbnail": {
                            "url": biome['thumbnail']
                            },
                        "fields": [
                            {
                                "name": "Time",
                                "value": f"<t:{int(time.time())}:T>, <t:{int(time.time())}:R>"
                            }
                        ],
                        "footer": {
                            "text": "My Biome Scanner"
                        }
                    }
                ]
            }
            result = requests.post(url, json = data)

            if result.status_code == 204: print("Message Sent!")
            else: print(f"Failed: {result.status_code}, {result.text}")

#------------------------
#--HELPERS
#------------------------

def load_json_from_github(raw_url):
    r = requests.get(raw_url)
    r.raise_for_status()  # throws if the file doesn't exist
    return r.json()

def userid_to_username(user_id):
    url = f"https://users.roblox.com/v1/users/{user_id}"
    r = requests.get(url)

    if r.status_code != 200:
        return None

    data = r.json()
    print(data.get("name"))
    return data.get("name")

def read_first_5_mb(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(5_000_000)  # 5 MB
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return ""

def parse_log_timestamp(ts: str):
    if not ts or len(ts) < 10:
        return None  # invalid timestamp

    ts = ts.rstrip("Z")

    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def seconds_since(ts):
    log_time = parse_log_timestamp(ts)
    if log_time is None:
        return None

    now = datetime.now(timezone.utc)
    return (now - log_time).total_seconds()


def tail_file(path, callback, interval=0.5):
    last_size = 0

    while True:
        try:
            size = os.path.getsize(path)

            # File grew → read only the new part
            if size > last_size:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(last_size)
                    new_data = f.read()
                    last_size = size

                    if new_data:
                        callback(new_data)

            # File shrank → log rotated or rewritten
            elif size < last_size:
                last_size = 0

            time.sleep(interval)

        except FileNotFoundError:
            # File deleted or rotated
            last_size = 0
            time.sleep(interval)

def read_last_valid_line(path):
    print(f"\n[DEBUG] Opening file: {path}")

    with open(path, "rb") as f:
        f.seek(0, 2)
        end = f.tell()
        print(f"[DEBUG] File size: {end} bytes")

        buffer = b""
        pos = end

        # Read backwards until we find a full line with a timestamp
        while pos > 0:
            pos -= 1
            f.seek(pos)
            char = f.read(1)

            if char == b"\n":
                print("[DEBUG] Newline found, decoding buffer...")

                line = buffer[::-1].decode("utf-8", errors="ignore").strip()
                print(f"[DEBUG] Candidate line: '{line}'")

                if line.startswith("20"):
                    print("[DEBUG] Valid timestamped line found!")
                    return line

                print("[DEBUG] Line does NOT start with '20', clearing buffer.")
                buffer = b""
            else:
                buffer += char

        print("[DEBUG] Reached start of file without finding a valid line.")
        return None

def load_biomes():
    try:
        print("[biomes] Fetching biome data from GitHub...")
        response = requests.get(biomes_url, timeout=5)
        response.raise_for_status()

        biomes = json.loads(response.text)
        print(f"[biomes] Loaded {len(biomes)} biomes from GitHub.")
        return biomes

    except Exception as e:
        print("[biomes] ERROR loading biomes:", e)
        return []

biomes = load_biomes()

#------------------------
#--SCANNER FUNCTIONS
#------------------------

def find_logs():
    roblox_logs_dir = Path(localappdata) / "Roblox" / "logs"

    if not roblox_logs_dir.exists():
        print("Roblox logs folder not found.")
        return []

    all_logs = list(roblox_logs_dir.glob("*.log"))

    # Filter out installer logs and return full paths
    logs = [log for log in all_logs if "installer" not in log.name.lower()]

    print(f"Found {len(logs)} Roblox log files:")
    for log in logs:
        print(" -", log.name)

    return logs


def identify_log():
    global assigned_log

    logs = find_logs()
    if not logs:
        print("[identify_log] No logs to process.")
        return

    username = userid_to_username(user_entry.get())
    if not username:
        print("[identify_log] Could not resolve username.")
        return

    print(f"[identify_log] Looking for logs containing username: {username}")

    # First pass: find logs that belong to this user + Sol's RNG
    linked_logs = []
    for log_path in logs:
        data = read_first_5_mb(log_path)
        if username in data and "Sol's RNG" in data:
            print(f"[identify_log] Linked log found: {log_path}")
            linked_logs.append(log_path)

    if not linked_logs:
        print("[identify_log] No linked logs found for this user.")
        return

    # Second pass: check timestamps on each linked log
    for path in linked_logs:
        print(f"[identify_log] Checking last valid line in: {path}")

        last_line = read_last_valid_line(path)
        if not last_line:
            print("[identify_log] No valid timestamped line found, skipping.")
            continue

        print(f"[identify_log] Last valid line: {last_line}")

        # Extract timestamp from CSV format (timestamp is before first comma)
        timestamp = last_line.split(",")[0].strip()
        print(f"[identify_log] Extracted timestamp: {timestamp}")

        time_since = seconds_since(timestamp)
        print(f"[identify_log] seconds_since() returned: {time_since}")

        if time_since is None:
            print("[identify_log] Timestamp parsing failed, skipping.")
            continue

        # ✔ Only assign if log is recent
        if time_since <= 30:
            assigned_log = path
            print(f"[identify_log] Assigned log: {assigned_log}")
            return  # STOP — we found the correct log

        print("[identify_log] Log is older than 30 seconds, moving on.")

    # If we finish the loop without finding a recent log:
    print("[identify_log] No logs updated within the last 30 seconds.")

def process_new_log_text(data):
    global current_biome
    lines = data.splitlines()
    for line in lines:
        for biome in biomes:
            if f'"hoverText":"{biome["name"]}","assetId":{biome["asset id"]}' in line:
                read_biome = biome["title"]
                if read_biome != current_biome:
                    send_biome_stop(current_biome)
                    print(f"Biome Stopped: {current_biome}")
                    send_biome_start(read_biome)
                    current_biome_label.configure(text = f"Current Biome: {read_biome}")
                    current_biome = read_biome
                    print(f"New Biome Found: {current_biome}")
                    return
            pass
                    

def scanner_loop():
    global scanning, assigned_log

    if not assigned_log:
        print("[scanner] No assigned log yet.")
        identify_log()
        time.sleep(0.1)
        return

    print("[scanner] Starting scanner loop...")

    # Open the file once
    with open(assigned_log, "r", encoding="utf-8", errors="ignore") as f:

        # 1. Seek to end (ignore old content)
        f.seek(0, os.SEEK_END)
        last_pos = f.tell()
        print(f"[scanner] Initial seeker at: {last_pos}")

        while scanning:
            try:
                current_size = os.path.getsize(assigned_log)

                # 2. If file grew, read only the new part
                if current_size > last_pos:
                    f.seek(last_pos)
                    new_data = f.read(current_size - last_pos)
                    last_pos = current_size

                    # 3. Process new lines for biomes
                    process_new_log_text(new_data)

                # 4. Sleep so UI stays responsive
                time.sleep(0.1)

            except Exception as e:
                print("[scanner] ERROR:", e)
                time.sleep(0.5)

                

        
#------------------------
#--LABELS
#------------------------

current_biome_label = ctk.CTkLabel(tab1, text = "Current Biome: ", font = ("arial", 20))
current_biome_label.grid(row=0,column=1,padx=20,pady=5)

user_label = ctk.CTkLabel(tab2, text = "Roblox User ID", font = ("arial", 20))
user_label.grid(row=0,column=2,padx=20,pady=5)

webhook_label = ctk.CTkLabel(tab2, text = "Webhook URL", font = ("arial", 20))
webhook_label.grid(row=0,column=1,padx=20,pady=5)

ps_label = ctk.CTkLabel(tab2, text = "Private Server Link", font = ("arial", 15))
ps_label.grid(row=0,column=0,padx=20,pady=5)

role_entries = {}

for index, biome in enumerate(biomes):
    global indexer
    biome_label = ctk.CTkLabel(scroll3, text = biome["title"], font = ("arial", 15))
    biome_label.grid(row=index,column=0,padx=20,pady=5)
    role_entry = ctk.CTkEntry(scroll3, placeholder_text = "Role ID(optional)", width = 200)
    role_entry.grid(row=index,column=1,padx=20,pady=5)

    role_entries[biome["title"]] = role_entry
    
    indexer = index

#------------------------
#--ENTRIES
#------------------------

webhook_entry = ctk.CTkEntry(tab2, placeholder_text = "Discord Webhook URL", width = 200)
webhook_entry.grid(row=1,column=1,padx=20,pady=5)

ps_entry = ctk.CTkEntry(tab2, placeholder_text = "Private Server Link", width = 200)
ps_entry.grid(row=1, column=0,padx=20,pady=5)

user_entry = ctk.CTkEntry(tab2, placeholder_text = "Roblox User ID", width = 200)
user_entry.grid(row=1,column=2,padx=20,pady=5)

#------------------------
#--BUTTONS
#------------------------

toggle_button = ctk.CTkButton(tab1, text="Start", command = toggle, fg_color = "#009C00", hover_color = "#016e01",width=200,height=50)
toggle_button.grid(row = 0, column = 0, padx=0, pady=0)

message_button = ctk.CTkButton(tab2,text="Send Test Message",command = test_message, fg_color = "#009C00", hover_color = "#016e01")
message_button.grid(row=2,column=1,padx=0,pady=0)

save_button = ctk.CTkButton(tab2, text="Save Settings", command = save_settings,width=150,height=40)
save_button.grid(row=3,column=1,padx = 0, pady=10)

save_roles = ctk.CTkButton(scroll3, text = "Save Roles", command = save_settings)
save_roles.grid(row=indexer+1,column=0,padx=0,pady=10)

#------------------------
#--Creating App and Loading Settings
#------------------------

def load_settings():
    if not os.path.exists(file_path):
        return  # No file yet

    # Read file content first
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read().strip()

    # If file is empty → skip loading
    if not content:
        print("settings.json is empty — skipping load.")
        return

    # Try to parse JSON safely
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        print("settings.json is corrupted — skipping load.")
        return

    # Load normal settings
    webhook_entry.insert(0, data.get("webhook url", ""))
    ps_entry.insert(0, data.get("ps link", ""))
    user_entry.insert(0, data.get("user id", ""))

    saved_roles = data.get("role ids", {})

    # Load biome role IDs
    for biome in biomes:
        title = biome["title"]
        if title in saved_roles:
            role_entries[title].insert(0, saved_roles[title])

            

load_settings()
app.mainloop()
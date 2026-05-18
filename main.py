import customtkinter as ctk
import tkinter as tk

import requests

import os
import json
from pathlib import Path

import threading

import time
from datetime import datetime, timezone

import pytesseract
from pytesseract import Output
from PIL import Image, ImageGrab
from rapidfuzz import fuzz, process
import numpy as np

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

scroll4 = ctk.CTkScrollableFrame(tab4)
scroll4.pack(fill="both", expand=True)

app_dir = os.path.join(os.getenv("LOCALAPPDATA"), "My Biome Scanner")
os.makedirs(app_dir, exist_ok=True)
file_path = os.path.join(app_dir, "settings.json")

localappdata = os.getenv("LOCALAPPDATA")

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

biomes_url = "https://raw.githubusercontent.com/akindem2/My-Biome-Tracker/refs/heads/main/biomes.json"

merchants_url = "https://raw.githubusercontent.com/akindem2/My-Biome-Tracker/refs/heads/main/merchants.json"

merchant_method = None
chat_box_coords = None

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
        if merchant_method == "ocr":
            merchant_thread = threading.Thread(target=merchant_loop, daemon=True)
            merchant_thread.start()
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

    merchant_roles = {}
    for merchant in merchants:
        name = merchant["name"]
        if name in merchant_entries:
            merchant_roles[name] = merchant_entries[name].get()

    settings = {
        "webhook url": webhook_entry.get(),
        "ps link": ps_entry.get(),
        "user id": user_entry.get(),
        "role ids": role_ids,
        "merchant roles": merchant_roles,
        "merchant webhook": merchant_wb_entry.get(),
        "merchant method": merchant_method,
        "chat box coords": chat_box_coords
    }
    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(settings, json_file, indent=4)

    print(f"Settings saved to {file_path}")


def test_message(webhook):
    url = webhook
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

def capture_screen_coordinates(callback, main_window=None):
    """
    Launches a transparent overlay. Passes the final (x1, y1, x2, y2) 
    tuple into the 'callback' function when finished.
    """
    # Hide the main window if it was passed in
    if main_window:
        main_window.iconify()

    # Initialize the overlay window using a Toplevel widget 
    # (Prevents it from fighting with the main window's mainloop)
    overlay = ctk.CTkToplevel()
    overlay.attributes("-fullscreen", True)
    overlay.attributes("-topmost", True)
    overlay.attributes("-alpha", 0.35)

    # Standard Tkinter Canvas for capturing pixel data
    canvas = tk.Canvas(overlay, cursor="cross", bg="#242424", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    start_x, start_y = None, None
    rect_id = None

    def on_button_press(event):
        nonlocal start_x, start_y, rect_id
        start_x, start_y = event.x, event.y
        rect_id = canvas.create_rectangle(start_x, start_y, start_x, start_y, outline='#1f538d', width=3)

    def on_move_press(event):
        nonlocal rect_id
        if rect_id:
            canvas.coords(rect_id, start_x, start_y, event.x, event.y)

    def on_button_release(event):
        x1, y1 = min(start_x, event.x), min(start_y, event.y)
        x2, y2 = max(start_x, event.x), max(start_y, event.y)
        
        overlay.destroy()  # Close the overlay
        
        if main_window:
            main_window.deiconify()  # Bring back main window
            
        callback((x1, y1, x2, y2))  # Send coordinates to our handler

    def on_cancel(event=None):
        overlay.destroy()
        if main_window:
            main_window.deiconify()
        callback(None)

    # Bind interactions
    canvas.bind("<ButtonPress-1>", on_button_press)
    canvas.bind("<B1-Motion>", on_move_press)
    canvas.bind("<ButtonRelease-1>", on_button_release)
    overlay.bind("<Escape>", on_cancel)

def handle_captured_coordinates(coords):
    global chat_box_coords
    if coords:
        chat_box_coords = coords
        x1, y1, x2, y2 = coords
        print(f"\n--- Box Captured ---")
        print(f"Top-Left: ({x1}, {y1})")
        print(f"Bottom-Right: ({x2}, {y2})")
        print(f"Size: {x2-x1}x{y2-y1}px")
        
        # Update the UI label with the results
        result_label.configure(text=f"Captured: {x2-x1}x{y2-y1} at ({x1}, {y1})")
    else:
        result_label.configure(text="Selection Canceled.")

def extract_color_from_bbox(image, x1, y1, x2, y2):
    """
    Crops the specific bounding box and isolates the text pixels from the 
    background to return their average RGB color.
    """
    img_width, img_height = image.size
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(img_width, x2), min(img_height, y2)
    
    if x2 <= x1 or y2 <= y1:
        print("[extract_color_from_bbox] WARNING: Invalid bounding box! Returning (0, 0, 0)")
        return (0, 0, 0)
        
    line_crop = image.crop((x1, y1, x2, y2)).convert("RGB")
    img_array = np.array(line_crop)
    
    # Isolate background using edge pixels. Use median to prevent text touching edges from skewing it.
    edge_pixels = np.concatenate([
        img_array[0, :, :], img_array[-1, :, :],
        img_array[:, 0, :], img_array[:, -1, :]
    ])
    bg_rgb = np.median(edge_pixels, axis=0)
    
    # Filter out background pixels to find the true text color
    all_pixels = img_array.reshape(-1, 3)
    distances_from_bg = np.linalg.norm(all_pixels - bg_rgb, axis=1)
    
    # Pick the "correct coordinates" by finding the pixels FURTHEST from the background.
    if len(distances_from_bg) > 0:
        max_dist = np.max(distances_from_bg)
        if max_dist > 30: # Ensure there is actual text visible against the background
            # Sample the multiple coordinates in the area that represent the PURE text color
            pure_text_pixels = all_pixels[distances_from_bg > max_dist * 0.85]
            detected_color = tuple(map(int, np.mean(pure_text_pixels, axis=0)))
            print(f"[extract_color_from_bbox] Successfully isolated text color: {detected_color}")
            return detected_color

    print("[extract_color_from_bbox] WARNING: No foreground text pixels isolated from background! Returning (0, 0, 0)")
    return (0, 0, 0)


def analyze_specific_text_and_color(image_input, target_statement, target_rgb):
    """
    Finds the specific line of text matching the target_statement, 
    then calculates text similarity and color similarity for THAT line only.
    """
    if isinstance(image_input, str):
        image_input = Image.open(image_input)
        
    # 1. Get detailed structural OCR data
    ocr_data = pytesseract.image_to_data(image_input, output_type=Output.DICT)
    
    # 2. Group Tesseract words into unique lines based on layout IDs
    # Tesseract groups layout by: block_num -> par_num -> line_num
    lines_dict = {}
    
    for i in range(len(ocr_data['text'])):
        word = ocr_data['text'][i].strip()
        if not word:
            continue
            
        # Create a unique key for the specific line
        line_key = (ocr_data['block_num'][i], ocr_data['par_num'][i], ocr_data['line_num'][i])
        
        if line_key not in lines_dict:
            lines_dict[line_key] = {"text_list": [], "indices": []}
            
        lines_dict[line_key]["text_list"].append(word)
        lines_dict[line_key]["indices"].append(i)

    # Reconstruct flat strings for each line
    reconstructed_lines = {}
    for key, data in lines_dict.items():
        reconstructed_lines[key] = " ".join(data["text_list"])

    if not reconstructed_lines:
        return 0.0, 0.0, "No text found", (0, 0, 0)

    # 3. Use RapidFuzz to find which reconstructed line matches our target statement best
    line_strings = list(reconstructed_lines.values())
    best_match_result = process.extractOne(target_statement, line_strings, scorer=fuzz.partial_ratio)
    
    if not best_match_result:
        return 0.0, 0.0, "No match found", (0, 0, 0)
        
    matched_text_string, text_score, matched_index = best_match_result
    
    # Retrieve the original layout key and word indices for the winning line
    best_line_key = list(reconstructed_lines.keys())[matched_index]
    matched_word_indices = lines_dict[best_line_key]["indices"]
    
    # 4. Extract color ONLY from the words in that winning line
    min_x = min([ocr_data['left'][i] for i in matched_word_indices])
    min_y = min([ocr_data['top'][i] for i in matched_word_indices])
    max_x = max([ocr_data['left'][i] + ocr_data['width'][i] for i in matched_word_indices])
    max_y = max([ocr_data['top'][i] + ocr_data['height'][i] for i in matched_word_indices])
    detected_rgb = extract_color_from_bbox(image_input, min_x, min_y, max_x, max_y)
    
    # 5. Calculate Color Similarity Score (Euclidean Distance mapped to 0-100%)
    r1, g1, b1 = detected_rgb
    r2, g2, b2 = target_rgb
    distance = np.sqrt((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2)
    
    max_distance = 441.673 # Max distance in 3D RGB space
    color_score = (1.0 - (distance / max_distance)) * 100
    
    return round(text_score, 2), round(color_score, 2), matched_text_string, detected_rgb

def run_analysis_on_chat_box():
    global chat_box_coords
    
    # 1. Safety check: Ensure the user actually selected a box first
    if chat_box_coords is None:
        print("Error: No coordinates captured yet! Click the button to select a region first.")
        result_label.configure(text="Error: Select a region first!")
        return

    print(f"Taking screenshot of region: {chat_box_coords}")
    
    # 2. Crop the exact region of the screen using the stored coordinates
    # ImageGrab.grab takes a tuple of (left, top, right, bottom)
    cropped_image = ImageGrab.grab(bbox=chat_box_coords)
    
    # Optional: Save it locally if you want to visually verify what it saw
    # cropped_image.save("last_detected_chat.png")
    
    # 3. Define what text and color you are expecting to find inside the box
    target_phrase = "Hello"      # Change this to whatever text you want to match
    target_rgb_color = (0, 255, 0) # Change this to your expected text color (e.g., Green)
    
    # 4. Run your targeted OCR + Color processor on the cropped image
    text_score, color_score, matched_text, detected_rgb = analyze_specific_text_and_color(
        cropped_image, 
        target_phrase, 
        target_rgb_color
    )
    
    # 5. Output the results
    print("\n" + "="*45)
    print("            OCR & COLOR ANALYSIS            ")
    print("="*45)
    print(f"Isolated Line Found : \"{matched_text}\"")
    print(f"Isolated Line Color : RGB {detected_rgb}")
    print("-"*45)
    print(f"TEXT SIMILARITY SCORE  : {text_score:.2f}%")
    print(f"COLOR SIMILARITY SCORE : {color_score:.2f}%")
    print("="*45)
    
    # Update your UI with the final metrics
    result_label.configure(
        text=f"Match: {text_score:.1f}% | Color Match: {color_score:.1f}%"
    )

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

def send_merchant_spawn(merchant_name, image = None):
    for merchant in merchants:
        if merchant_name == merchant["name"]:
            
            # --- CONVERT RGB STRING TO DISCORD COLOR ---
            color_str = merchant["color"].replace("(", "").replace(")", "")
            r, g, b = map(int, color_str.split(","))
            discord_color = (r << 16) + (g << 8) + b 
            # -------------------------------------------

            content = ""
            # Fixed nested quote issue here (changed "name" to 'name'):
            if merchant["name"] in merchant_entries and merchant_entries[merchant["name"]].get():
                content = f"<@&{merchant_entries[merchant['name']].get()}>"
                
            if merchant_wb_entry.get():
                url = merchant_wb_entry.get()
            else:
                url = webhook_entry.get()
            
            if not url: return
            
            data = {
                "content": content,
                "embeds": [
                    {
                        "title": f"{merchant['name']} Spawned!",
                        "color": discord_color, # <--- Updated to use converted color
                        "thumbnail": {
                            "url": merchant['thumbnail']
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

            if image:
                if isinstance(image, str):
                    data["embeds"][0]["image"] = {
                        "url": image
                    }
                    result = requests.post(url, json=data)
                else:
                    # It's a PIL Image object
                    import io
                    img_byte_arr = io.BytesIO()
                    image.save(img_byte_arr, format='PNG')
                    img_byte_arr.seek(0)
                    
                    data["embeds"][0]["image"] = {
                        "url": "attachment://screenshot.png"
                    }
                    # Discord requires multipart/form-data for files + JSON payload
                    result = requests.post(url, data={"payload_json": json.dumps(data)}, files={"screenshot.png": img_byte_arr})
            else:
                result = requests.post(url, json = data)

            if result.status_code == 204: 
                print("Message Sent!")
            else: 
                print(f"Failed: {result.status_code}, {result.text}")

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

def load_merchants():
    try:
        print("[merchants] Fetching merchant data from GitHub...")
        response = requests.get(merchants_url, timeout=5)
        response.raise_for_status()

        merchants = json.loads(response.text)
        print(f"[merchants] Loaded {len(merchants)} merchants from GitHub.")
        return merchants

    except Exception as e:
        print("[merchants] ERROR loading merchants:", e)
        return []

biomes = load_biomes()
merchants = load_merchants()

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
        for merchant in merchants:
            if merchant_method == "log":
                if str(merchant["asset id"]) in line:
                    send_merchant_spawn(merchant["name"])
                    print(f"Merchant Spawned: {merchant['title']}")
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
        time.sleep(0.5)
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

def merchant_loop():
    global scanning, chat_box_coords
    print(f"[merchant_loop] Merchant loop started with method: {merchant_method}")
    if merchant_method != "ocr":
        return

    if chat_box_coords is None:
        print("[merchant_loop] OCR method selected but no chat box coordinates captured. Please align chat box.")
        return

    print(f"[merchant_loop] OCR detection started using chat box coords: {chat_box_coords}")

    # Keep track of last spawn notification time for each merchant to avoid duplicate notifications
    last_spawn_time = {} # merchant_name -> timestamp

    while scanning:
        if merchant_method != "ocr":
            break
        
        try:
            # Capture the exact region of the screen using the stored coordinates
            cropped_image = ImageGrab.grab(bbox=chat_box_coords)
            
            # Run OCR structure detection
            ocr_data = pytesseract.image_to_data(cropped_image, output_type=Output.DICT)
            
            # Group Tesseract words into unique lines based on layout IDs
            lines_dict = {}
            raw_words = []
            for i in range(len(ocr_data['text'])):
                word = ocr_data['text'][i].strip()
                if not word:
                    continue
                raw_words.append(word)
                line_key = (ocr_data['block_num'][i], ocr_data['par_num'][i], ocr_data['line_num'][i])
                if line_key not in lines_dict:
                    lines_dict[line_key] = {"text_list": [], "indices": []}
                lines_dict[line_key]["text_list"].append(word)
                lines_dict[line_key]["indices"].append(i)
            
            if raw_words:
                print(f"[merchant_loop] OCR detected {len(raw_words)} words: {raw_words}")
            else:
                print(f"[merchant_loop] OCR detected 0 words in the current region.")
            
            reconstructed_lines = {}
            for key, data in lines_dict.items():
                reconstructed_lines[key] = " ".join(data["text_list"])
            
            if reconstructed_lines:
                print(f"[merchant_loop] Reconstructed {len(reconstructed_lines)} lines:")
                for key, data in reconstructed_lines.items():
                    print(f"  - Line {key}: '{data}'")
                
                line_strings = list(reconstructed_lines.values())
                
                # Check each merchant
                for merchant in merchants:
                    name = merchant["name"]
                    target_message = merchant["message"]
                    
                    # Extract target RGB color from JSON color string, e.g. "(246, 132, 66)"
                    color_str = merchant["color"]
                    target_rgb = tuple(map(int, color_str.replace("(", "").replace(")", "").split(",")))
                    
                    # Find if any reconstructed line matches this merchant's message
                    best_match_result = process.extractOne(target_message, line_strings, scorer=fuzz.partial_ratio)
                    if best_match_result:
                        matched_text, text_score, matched_index = best_match_result
                        
                        # Print partial matches to help debug why text similarity might be lower than expected
                        if text_score > 30:
                            print(f"[merchant_loop] Comparing '{name}': Target='{target_message}' vs BestMatch='{matched_text}' (Score: {text_score:.1f}%)")
                        
                        # Check text similarity (threshold 85%)
                        if text_score > 85:
                            # Now check color similarity
                            best_line_key = list(reconstructed_lines.keys())[matched_index]
                            matched_word_indices = lines_dict[best_line_key]["indices"]
                            
                            # Extract coordinates of the matched text
                            min_x = min([ocr_data['left'][i] for i in matched_word_indices])
                            min_y = min([ocr_data['top'][i] for i in matched_word_indices])
                            max_x = max([ocr_data['left'][i] + ocr_data['width'][i] for i in matched_word_indices])
                            max_y = max([ocr_data['top'][i] + ocr_data['height'][i] for i in matched_word_indices])
                            
                            abs_x1 = chat_box_coords[0] + min_x
                            abs_y1 = chat_box_coords[1] + min_y
                            abs_x2 = chat_box_coords[0] + max_x
                            abs_y2 = chat_box_coords[1] + max_y
                            
                            print(f"[merchant_loop] Matched text screen coordinates: ({abs_x1}, {abs_y1}) to ({abs_x2}, {abs_y2})")
                            
                            detected_rgb = extract_color_from_bbox(cropped_image, min_x, min_y, max_x, max_y)
                            print(f"[merchant_loop] Text matched for '{name}' (Score: {text_score:.1f}%). Extracted color: {detected_rgb} (Target: {target_rgb})")
                            
                            # Calculate Color Similarity Score
                            r1, g1, b1 = detected_rgb
                            r2, g2, b2 = target_rgb
                            distance = np.sqrt((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2)
                            max_distance = 441.673 # Max distance in 3D RGB space
                            color_score = (1.0 - (distance / max_distance)) * 100
                            print(f"[merchant_loop] Color similarity for '{name}': {color_score:.1f}% (Required: > 80%)")
                            
                            # If both text and color match well
                            if color_score > 80:
                                current_time = time.time()
                                # Cooldown of 20 minutes (1200 seconds) to prevent spamming
                                if name not in last_spawn_time or (current_time - last_spawn_time[name]) > 1200:
                                    last_spawn_time[name] = current_time
                                    print(f"[merchant_loop] OCR MATCH SUCCESS! {name} detected. Text match: {text_score:.1f}%, Color match: {color_score:.1f}%")
                                    send_merchant_spawn(name, image=cropped_image)
                                else:
                                    remaining = 1200 - (current_time - last_spawn_time[name])
                                    print(f"[merchant_loop] OCR Match! '{name}' detected but skipped due to active cooldown ({remaining:.0f}s left)")
                                    
        except Exception as e:
            import traceback
            print("[merchant_loop] ERROR encountered during OCR loop:", e)
            traceback.print_exc()
            
        time.sleep(2.0)

        
#------------------------
#--HOME TAB
#------------------------

current_biome_label = ctk.CTkLabel(tab1, text = "Current Biome: ", font = ("arial", 20))
current_biome_label.grid(row=0,column=1,padx=20,pady=5)

toggle_button = ctk.CTkButton(tab1, text="Start", command = toggle, fg_color = "#009C00", hover_color = "#016e01",width=200,height=50)
toggle_button.grid(row = 0, column = 0, padx=0, pady=0)

#------------------------
#--SETTINGS TAB
#------------------------

##LABELS
user_label = ctk.CTkLabel(tab2, text = "Roblox User ID", font = ("arial", 20))
user_label.grid(row=0,column=2,padx=20,pady=5)

webhook_label = ctk.CTkLabel(tab2, text = "Webhook URL", font = ("arial", 20))
webhook_label.grid(row=0,column=1,padx=20,pady=5)

ps_label = ctk.CTkLabel(tab2, text = "Private Server Link", font = ("arial", 15))
ps_label.grid(row=0,column=0,padx=20,pady=5)


##Entries
webhook_entry = ctk.CTkEntry(tab2, placeholder_text = "Discord Webhook URL", width = 200)
webhook_entry.grid(row=1,column=1,padx=20,pady=5)

ps_entry = ctk.CTkEntry(tab2, placeholder_text = "Private Server Link", width = 200)
ps_entry.grid(row=1, column=0,padx=20,pady=5)

user_entry = ctk.CTkEntry(tab2, placeholder_text = "Roblox User ID", width = 200)
user_entry.grid(row=1,column=2,padx=20,pady=5)


##Buttons
message_button = ctk.CTkButton(tab2,text="Send Test Message",command = lambda: test_message(webhook_entry.get()), fg_color = "#009C00", hover_color = "#016e01")
message_button.grid(row=2,column=1,padx=0,pady=0)

save_button = ctk.CTkButton(tab2, text="Save Settings", command = save_settings,width=150,height=40)
save_button.grid(row=3,column=1,padx = 0, pady=10)

#------------------------
#--BIOMES TAB
#------------------------

biomes_ids_label = ctk.CTkLabel(scroll3, text = "Biome Role ID's(optional)", font = ("arial", 15))
biomes_ids_label.grid(row=0,column=1,padx=20,pady=0)

role_entries = {}

for index, biome in enumerate(biomes):
    biome_label = ctk.CTkLabel(scroll3, text = biome["title"], font = ("arial", 15))
    biome_label.grid(row=index+1,column=0,padx=20,pady=5)
    role_entry = ctk.CTkEntry(scroll3, placeholder_text = "Role ID(optional)", width = 200)
    role_entry.grid(row=index+1,column=1,padx=20,pady=5)

    role_entries[biome["title"]] = role_entry

save_roles = ctk.CTkButton(scroll3, text = "Save Roles", command = save_settings)
save_roles.grid(row=len(biomes)+2,column=0,padx=0,pady=10)

#------------------------
#--MERCHANT TAB
#------------------------

merchant_ocr_var = ctk.BooleanVar(value=False)
merchant_log_var = ctk.BooleanVar(value=False)

def enforce_mutual_exclusion(clicked_box):
    global merchant_method
    if clicked_box == "ocr" and merchant_ocr_var.get():
        merchant_log_var.set(False)
        merchant_method = "ocr"
        
    elif clicked_box == "log" and merchant_log_var.get():
        merchant_ocr_var.set(False)
        merchant_method = "log"
        
    else:
        merchant_method = None

    print(f"Selected Merchant Method: {merchant_method}")

merchant_ocr_check_box = ctk.CTkCheckBox(scroll4, text = "Enable OCR Merchant Detection", font = ("arial", 15),variable = merchant_ocr_var, command = lambda: enforce_mutual_exclusion("ocr"))
merchant_ocr_check_box.grid(row=0,column=2,padx=20,pady=5)

merchant_log_check_box = ctk.CTkCheckBox(scroll4, text = "Enable Log-Based Merchant Detection(requires fix)", font = ("arial", 10),variable = merchant_log_var, command = lambda: enforce_mutual_exclusion("log"))
merchant_log_check_box.grid(row=1,column=2,padx=20,pady=5)

merchant_wb_entry = ctk.CTkEntry(scroll4, placeholder_text = "Merchant Webhook(optional)", font = ("arial", 15), width=250)
merchant_wb_entry.grid(row=2,column=2,padx=20,pady=10)

merchants_ids_label = ctk.CTkLabel(scroll4, text = "Merchant Role ID's(optional)", font = ("arial", 15))
merchants_ids_label.grid(row=0,column=1,padx=20,pady=0)

ocr_align_button = ctk.CTkButton(scroll4, text = "Align Chat Box", command=lambda: capture_screen_coordinates(handle_captured_coordinates, main_window=app))
ocr_align_button.grid(row=4,column=1,padx=20,pady=10)

result_label = ctk.CTkLabel(scroll4, text = "Coordinates will appear here...", font = ("arial", 12))
result_label.grid(row=4,column=2,padx=20,pady=10)

test_merchant = ctk.CTkButton(scroll4, text = "Test Merchant Webhook", command = lambda: test_message(merchant_wb_entry.get()))
test_merchant.grid(row=3,column=2,padx=20,pady=10)

merchant_entries = {}

for index, merchant in enumerate(merchants):
    merchant_label = ctk.CTkLabel(scroll4, text = merchant['name'], font = ("arial", 15))
    merchant_label.grid(row=index+1,column=0,padx=20,pady=5  )

    merchant_entry = ctk.CTkEntry(scroll4, placeholder_text = f"{merchant['name']} Role ID(Optional)", font = ("arial", 15))
    merchant_entry.grid(row=index+1,column=1,padx=20,pady=5)
    
    merchant_entries[merchant["name"]] = merchant_entry

save_merchants = ctk.CTkButton(scroll4, text = "Save Merchant Settings", command = save_settings)
save_merchants.grid(row=len(merchants)+1,column=0,padx=0,pady=10)

#------------------------
#--Creating App and Loading Settings
#------------------------

def load_settings():
    global chat_box_coords
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

    # Load merchant webhook
    if "merchant webhook" in data:
        merchant_wb_entry.insert(0, data.get("merchant webhook"))

    # Load merchant method
    loaded_method = data.get("merchant method")
    if loaded_method == "ocr":
        merchant_ocr_var.set(True)
        enforce_mutual_exclusion("ocr")
    elif loaded_method == "log":
        merchant_log_var.set(True)
        enforce_mutual_exclusion("log")

    # Load merchant role IDs
    saved_merchant_roles = data.get("merchant roles", {})
    for merchant in merchants:
        name = merchant["name"]
        if name in saved_merchant_roles and name in merchant_entries:
            merchant_entries[name].insert(0, saved_merchant_roles[name])

    # Load chat box coords
    chat_box_coords = data.get("chat box coords")
    if chat_box_coords and len(chat_box_coords) == 4:
        x1, y1, x2, y2 = chat_box_coords
        result_label.configure(text=f"Captured: {x2-x1}x{y2-y1} at ({x1}, {y1})")


load_settings()
app.mainloop()
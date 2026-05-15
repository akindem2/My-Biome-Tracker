import customtkinter as ctk

import requests

import os
import json

app_dir = os.path.join(os.getenv("LOCALAPPDATA"), "My Biome Scanner")
os.makedirs(app_dir, exist_ok=True)
file_path = os.path.join(app_dir, "settings.json")

def toggle():
    if toggle_button.cget("text") == "Start":
        toggle_button.configure(text = "Stop", fg_color = "#FF0000", hover_color = "#ff6161")
        send_start_message()
    else:
        toggle_button.configure(text = "Start", fg_color = "#009C00", hover_color = "#016e01")
        send_stop_message()

def save_settings():
    settings = {
        "webhook url": webhook_entry.get(),
        "ps link": ps_entry.get(),
    }
    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(settings, json_file)

    print(f"Settings saved to {file_path}")
def test_message():
    url = webhook_entry.get()
    data = {
        "embeds": [  # Note the start of the list
            {
                "title": "Test Message",
                "description": "Test message for Jane Juliet",
                "color": 0x00FF00,
                "footer": {
                    "text": "My Biome Scanner"
                }
            }
        ]
    }
    requests.post(url, json = data)

def send_start_message():
    url = webhook_entry.get()
    data = {
        "embeds": [
            {
                "title": "Macro Started",
                "description": "My Biome Tracker has started!",
                "color": 0x00FF00,
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
                "footer": {
                    "text": "My Biome Scanner"
                }
            }
        ]
    }
    result = requests.post(url, json = data)

    if result.status_code == 204: print("Message Sent!")
    else: print(f"Failed: {result.status_code}, {result.text}")

app = ctk.CTk()
app.geometry("800x300")
app.title("Biome Scanner")

#------------------------
#LABELS
#------------------------
current_biomes_label = ctk.CTkLabel(app, text = "Current Biome: ", font = ("arial", 20))
current_biomes_label.grid(row=0,column=1,padx=20,pady=20)



#------------------------
#ENTRIES
#------------------------
webhook_entry = ctk.CTkEntry(app, placeholder_text = "Discord Webhook URL", width = 200)
webhook_entry.grid(row=1,column=0,padx=20,pady=5)

ps_entry = ctk.CTkEntry(app, placeholder_text = "Private Server Link", width = 200)
ps_entry.grid(row=2, column=0,padx=20,pady=20)



#------------------------
#BUTTONS
#------------------------
toggle_button = ctk.CTkButton(app, text="Start", command = toggle, fg_color = "#009C00", hover_color = "#016e01",width=200,height=50)
toggle_button.grid(row = 0, column = 0, padx=0, pady=0)

message_button = ctk.CTkButton(app,text="Send Test Message",command = test_message, fg_color = "#009C00", hover_color = "#016e01")
message_button.grid(row=1,column=1,padx=0,pady=5)

save_button = ctk.CTkButton(app,text="Save Settings", command = save_settings,width=150,height=40)
save_button.grid(row=3,column=0,padx = 0, pady=0)

def load_settings():
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            # ctk Entry .insert requires (index, string)
            webhook_entry.insert(0, data.get("webhook url", ""))
            ps_entry.insert(0, data.get("ps link", ""))

load_settings()
app.mainloop()
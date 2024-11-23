import vlc
import os
from flask import Flask, jsonify
import requests
from threading import Thread
import warnings
import logging
from waitress import serve
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import threading


app = Flask(__name__)
player = None
partner_url = None

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
app.logger.disabled = True

warnings.filterwarnings("ignore")

@app.route('/play')
def remote_play():
    if player:
        player.play()
        return jsonify({"status": "success", "action": "play"})
    return jsonify({"status": "error", "message": "Player not initialized"})

@app.route('/pause')
def remote_pause():
    if player:
        player.pause()
        return jsonify({"status": "success", "action": "pause"})
    return jsonify({"status": "error", "message": "Player not initialized"})

@app.route('/seek/<int:seconds>')
def remote_seek(seconds):
    if player:
        player.set_time(seconds * 1000)  # Seek to the absolute time
        return jsonify({"status": "success", "action": "seek", "time": seconds})
    return jsonify({"status": "error", "message": "Player not initialized"})

@app.route('/stop')
def remote_stop():
    if player:
        player.stop()
        return jsonify({"status": "success", "action": "stop"})
    return jsonify({"status": "error", "message": "Player not initialized"})

def start_server():
    serve(app, host='0.0.0.0', port=5000)

def send_command(command, params=None):
    if not partner_url:
        app_status.set("Partner URL not set.")
        return False  # Indicate failure to send the command

    def perform_request():
        nonlocal command, params
        app_status.set("Trying to connect with partner...")
        retries = 3
        for attempt in range(retries):
            try:
                if params:
                    url = f"{partner_url}/{command}/{params}"
                else:
                    url = f"{partner_url}/{command}"
                response = requests.get(url, timeout=5)  # Increased timeout
                if response.status_code == 200:
                    app_status.set("Connected successfully.")
                    return True  # Command sent successfully
            except requests.exceptions.RequestException as e:
                print(f"Failed to send command to partner: {command}. Attempt {attempt + 1} of {retries}. Error: {e}")
                app_status.set(f"Failed to connect. Retrying... ({attempt + 1}/{retries})")
                if attempt < retries - 1:
                    time.sleep(0.5)  # Wait before retrying
        app_status.set("Failed to connect to partner.")
        return False  # Command sending failed

    # Run the request in a separate thread and return its result
    result = threading.Thread(target=perform_request, daemon=True).start()
    return result


def parse_time_to_seconds(hhmmss):
    try:
        parts = hhmmss.split(".")
        hours = int(parts[0]) if len(parts) > 0 else 0
        minutes = int(parts[1]) if len(parts) > 1 else 0
        seconds = int(parts[2]) if len(parts) > 2 else 0
        return hours * 3600 + minutes * 60 + seconds
    except ValueError:
        messagebox.showerror("Error", "Invalid time format. Please use HH.MM.SS format.")
        return None

def format_time(milliseconds):
    seconds = milliseconds // 1000
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}"

class VideoPlayerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Player")
        self.file_path = None

        global player
        instance = vlc.Instance("--quiet")
        player = instance.media_player_new()

        # Partner URL
        tk.Label(root, text="Partner URL:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.partner_url_entry = tk.Entry(root, width=40)
        self.partner_url_entry.grid(row=0, column=1, padx=10, pady=5)

        # Status Message
        global app_status
        app_status = tk.StringVar()
        app_status.set("Idle")
        tk.Label(root, textvariable=app_status, fg="blue").grid(row=1, column=0, columnspan=2, pady=5)

        # Select File
        tk.Button(root, text="Select Video File", command=self.select_file).grid(row=2, column=0, columnspan=2, pady=5)

        # Playback Controls
        tk.Button(root, text="Play", command=self.play).grid(row=3, column=0, padx=10, pady=5)
        tk.Button(root, text="Pause", command=self.pause).grid(row=3, column=1, padx=10, pady=5)
        tk.Button(root, text="Stop", command=self.stop).grid(row=4, column=0, padx=10, pady=5)

        # Seek
        tk.Label(root, text="Seek (seconds):").grid(row=5, column=0, sticky="w", padx=10, pady=5)
        self.seek_entry = tk.Entry(root, width=10)
        self.seek_entry.grid(row=5, column=1, padx=10, pady=5)
        tk.Button(root, text="Seek", command=self.seek).grid(row=6, column=0, columnspan=2, pady=5)

        # Seek to Time
        tk.Label(root, text="Seek to (HH.MM.SS):").grid(row=7, column=0, sticky="w", padx=10, pady=5)
        self.seek_time_entry = tk.Entry(root, width=10)
        self.seek_time_entry.grid(row=7, column=1, padx=10, pady=5)
        tk.Button(root, text="Seek to Time", command=self.seek_to_time).grid(row=8, column=0, columnspan=2, pady=5)

        # Media Info
        tk.Button(root, text="Show Info", command=self.show_info).grid(row=9, column=0, columnspan=2, pady=5)

        # Exit
        tk.Button(root, text="Exit", command=self.exit_app).grid(row=10, column=0, columnspan=2, pady=5)

    def select_file(self):
        self.file_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4;*.avi;*.mkv")])
        if not self.file_path:
            return
        if not os.path.exists(self.file_path):
            messagebox.showerror("Error", "File does not exist. Please try again.")
            return
        media = player.get_instance().media_new(self.file_path)
        player.set_media(media)
        messagebox.showinfo("Info", f"File loaded: {self.file_path}")

    def play(self):
        self.set_partner_url()
        if send_command("play"):
            player.play()
    
    def pause(self):
        self.set_partner_url()
        if send_command("pause"):
            player.pause()
    
    def stop(self):
        self.set_partner_url()
        if send_command("stop"):
            player.stop()
    
    def seek(self):
        self.set_partner_url()
        try:
            seconds = int(self.seek_entry.get())
            if send_command("seek", seconds):
                player.set_time(seconds * 1000)
        except ValueError:
            messagebox.showerror("Error", "Invalid input. Please enter a number.")
    
    def seek_to_time(self):
        self.set_partner_url()
        time_input = self.seek_time_entry.get()
        seconds = parse_time_to_seconds(time_input)
        if seconds is not None and send_command("seek", seconds):
            player.set_time(seconds * 1000)
    

    def show_info(self):
        if player:
            duration = player.get_length()
            current_time = player.get_time()
            if duration > 0 and current_time >= 0:
                remaining_time = duration - current_time
                messagebox.showinfo(
                    "Media Info",
                    f"Total Duration: {format_time(duration)}\n"
                    f"Current Position: {format_time(current_time)}\n"
                    f"Time Remaining: {format_time(remaining_time)}"
                )
            else:
                messagebox.showwarning("Warning", "Unable to retrieve media information.")
        else:
            messagebox.showerror("Error", "Player is not initialized.")

    def set_partner_url(self):
        global partner_url
        partner_url = self.partner_url_entry.get().strip()

    def exit_app(self):
        player.stop()
        self.root.quit()

if __name__ == "__main__":
    Thread(target=start_server, daemon=True).start()
    root = tk.Tk()
    app = VideoPlayerApp(root)
    root.mainloop()

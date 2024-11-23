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
from tkinter import filedialog, messagebox, ttk
import threading


app = Flask(__name__)
player = None
partner_url = None
file_loaded = False


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

@app.route('/is_file_loaded')
def is_file_loaded():
    return jsonify({"status": "success", "file_loaded": file_loaded})

@app.route('/load_file', methods=['POST'])
def load_file():
    global file_loaded
    file_loaded = True
    return jsonify({"status": "success", "action": "file loaded"})

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

    # Run the request synchronously and return the result
    return perform_request()


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
        tk.Button(root, text="Play", command=self.play).grid(row=3, column=0, padx=3, pady=5)
        tk.Button(root, text="Pause", command=self.pause).grid(row=3, column=1, padx=3, pady=5)
        tk.Button(root, text="Stop", command=self.stop).grid(row=3, column=2, padx=3, pady=5)

        # Progress Bar
        tk.Label(root, text="Progress:").grid(row=5, column=0, sticky="w", padx=10, pady=5)
        self.progress_bar = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.grid(row=5, column=1, padx=10, pady=5)
        self.progress_label = tk.Label(root, text="00:00:00 / 00:00:00")
        self.progress_label.grid(row=6, column=0, columnspan=2, pady=5)

        # Seek
        tk.Label(root, text="Seek (seconds):").grid(row=7, column=0, sticky="w", padx=5, pady=5)
        self.seek_entry = tk.Entry(root, width=10)
        self.seek_entry.grid(row=7, column=1, padx=5, pady=5)
        tk.Button(root, text="Seek", command=self.seek).grid(row=7, column=2, columnspan=1, pady=5)

        # Seek to Time
        tk.Label(root, text="Seek to (HH.MM.SS):").grid(row=9, column=0, sticky="w", padx=10, pady=5)
        self.seek_time_entry = tk.Entry(root, width=10)
        self.seek_time_entry.grid(row=9, column=1, padx=10, pady=5)
        tk.Button(root, text="Seek to Time", command=self.seek_to_time).grid(row=9, column=2, columnspan=1, pady=5)

        # Media Info
        tk.Button(root, text="Show Info", command=self.show_info).grid(row=11, column=0, columnspan=2, pady=5)

        # Exit
        tk.Button(root, text="Exit", command=self.exit_app).grid(row=11, column=1, columnspan=2, pady=5)

        # Update Progress
        self.update_progress()

    def update_progress(self):
        """Update the progress bar and label."""
        if player:
            current_time = player.get_time()  # Current time in milliseconds
            total_time = player.get_length()  # Total duration in milliseconds
            if total_time > 0:
                progress = (current_time / total_time) * 100
                self.progress_bar["value"] = progress
                self.progress_label.config(
                    text=f"{format_time(current_time)} / {format_time(total_time)}"
                )
        self.root.after(500, self.update_progress)  # Update every 500ms

    def select_file(self):
        self.file_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4;*.avi;*.mkv")])
        if not self.file_path:
            return
        if not os.path.exists(self.file_path):
            messagebox.showerror("Error", "File does not exist. Please try again.")
            return

        media = player.get_instance().media_new(self.file_path)
        player.set_media(media)

        # Mark file as loaded locally
        requests.post("http://127.0.0.1:5000/load_file")  # Update local Flask server status

        # Notify partner device
        self.set_partner_url()
        if not send_command("load_file"):
            messagebox.showwarning("Warning", "Failed to notify partner about file load.")

        # Check partner status
        if not self.check_partner_file_status():
            messagebox.showwarning("Warning", "Partner device has not loaded the file yet.")
        else:
            messagebox.showinfo("Info", f"File loaded: {self.file_path}")

    def check_partner_file_status(self):
        if not partner_url:
            app_status.set("Partner URL not set.")
            return False

        try:
            response = requests.get(f"{partner_url}/is_file_loaded", timeout=5)
            if response.status_code == 200 and response.json().get("file_loaded"):
                return True
        except requests.exceptions.RequestException as e:
            print(f"Error checking partner file status: {e}")
        return False


    def play(self):
        self.set_partner_url()
        if not self.check_partner_file_status():
            messagebox.showwarning("Warning", "File not loaded on both devices.")
            return
        if send_command("play"):  # Execute on partner first
            player.play()  # Play on local only if successful on partner
    
    def pause(self):
        self.set_partner_url()
        if not self.check_partner_file_status():
            messagebox.showwarning("Warning", "File not loaded on both devices.")
            return
        if send_command("pause"):  # Execute on partner first
            player.pause()  # Pause on local only if successful on partner
    
    def stop(self):
        self.set_partner_url()
        if not self.check_partner_file_status():
            messagebox.showwarning("Warning", "File not loaded on both devices.")
            return
        if send_command("stop"):  # Execute on partner first
            player.stop()  # Stop on local only if successful on partner
            self.progress_bar["value"] = 0  # Reset the progress bar
            self.progress_label.config(text="00:00:00 / 00:00:00")  # Reset the label text
    
    
    def seek(self):
        self.set_partner_url()
        try:
            seconds = int(self.seek_entry.get())
            if send_command("seek", seconds):  # Execute on partner first
                player.set_time(seconds * 1000)  # Seek on local only if successful on partner
        except ValueError:
            messagebox.showerror("Error", "Invalid input. Please enter a number.")
    
    def seek_to_time(self):
        self.set_partner_url()
        time_input = self.seek_time_entry.get()
        seconds = parse_time_to_seconds(time_input)
        if seconds is not None and send_command("seek", seconds):  # Execute on partner first
            player.set_time(seconds * 1000)  # Seek on local only if successful on partner

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

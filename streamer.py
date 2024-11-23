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

app = Flask(__name__)
player = None
partner_url = None
partner_file_loaded = False
local_file_loaded = False

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
app.logger.disabled = True

warnings.filterwarnings("ignore")


@app.route('/file_loaded', methods=['GET'])
def file_loaded():
    """Endpoint to confirm the file is loaded on the partner device."""
    return jsonify({"status": "success", "file_loaded": local_file_loaded})


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
                    return response.json()  # Return the JSON response
            except requests.exceptions.RequestException as e:
                print(f"Failed to send command to partner: {command}. Attempt {attempt + 1} of {retries}. Error: {e}")
                app_status.set(f"Failed to connect. Retrying... ({attempt + 1}/{retries})")
                if attempt < retries - 1:
                    time.sleep(0.5)  # Wait before retrying
        app_status.set("Failed to connect to partner.")
        return None  # Command sending failed

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
        app_status.set("No file chosen.")
        self.status_label = tk.Label(root, textvariable=app_status, fg="blue")
        self.status_label.grid(row=1, column=0, columnspan=2, pady=5)

        # Select File
        tk.Button(root, text="Select Video File", command=self.select_file).grid(row=2, column=0, columnspan=2, pady=5)

        # Playback Controls
        self.play_button = tk.Button(root, text="Play", command=self.play, state=tk.DISABLED)
        self.play_button.grid(row=3, column=0, padx=3, pady=5)
        self.pause_button = tk.Button(root, text="Pause", command=self.pause, state=tk.DISABLED)
        self.pause_button.grid(row=3, column=1, padx=3, pady=5)
        self.stop_button = tk.Button(root, text="Stop", command=self.stop, state=tk.DISABLED)
        self.stop_button.grid(row=3, column=2, padx=3, pady=5)

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
        global local_file_loaded
        self.file_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4;*.avi;*.mkv")])
        if not self.file_path:
            return
        if not os.path.exists(self.file_path):
            messagebox.showerror("Error", "File does not exist. Please try again.")
            return
        media = player.get_instance().media_new(self.file_path)
        player.set_media(media)
        local_file_loaded = True
        app_status.set("File loaded locally. Checking partner...")

        partner_status = send_command("file_loaded")
        if partner_status and partner_status.get("file_loaded"):
            app_status.set("File loaded in both devices.")
            self.enable_controls()
        else:
            app_status.set("File not loaded on partner. Controls disabled.")

    def enable_controls(self):
        """Enable all playback controls."""
        self.play_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.NORMAL)

    def play(self):
        self.set_partner_url()
        if send_command("play"):  # Execute on partner first
            player.play()  # Play on local only if successful on partner

    def pause(self):
        self.set_partner_url()
        if send_command("pause"):
            player.pause()

    def stop(self):
        self.set_partner_url()
        if send_command("stop"):
            player.stop()

    def seek(self):
        seek_time = self.seek_entry.get()
        try:
            seconds = int(seek_time)
            if send_command("seek", seconds):
                player.set_time(seconds * 1000)
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid integer for seconds.")

    def seek_to_time(self):
        time_value = self.seek_time_entry.get()
        seconds = parse_time_to_seconds(time_value)
        if seconds is not None and send_command("seek", seconds):
            player.set_time(seconds * 1000)

    def show_info(self):
        if player:
            info = (
                f"Media Path: {self.file_path}\n"
                f"Player State: {player.get_state()}\n"
                f"Current Time: {format_time(player.get_time())}\n"
                f"Total Duration: {format_time(player.get_length())}"
            )
            messagebox.showinfo("Media Information", info)

    def exit_app(self):
        self.stop()
        self.root.destroy()

    def set_partner_url(self):
        """Set the partner's URL from the entry field."""
        global partner_url
        url = self.partner_url_entry.get().strip()
        if url and url != partner_url:
            partner_url = url


if __name__ == "__main__":
    server_thread = Thread(target=start_server, daemon=True)
    server_thread.start()

    root = tk.Tk()
    app = VideoPlayerApp(root)
    root.mainloop()

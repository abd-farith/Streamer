import vlc
import os
from flask import Flask, jsonify
import requests
from threading import Thread
import warnings
import logging
from waitress import serve

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
        current_time = player.get_time() // 1000
        new_time = current_time + seconds
        player.set_time(new_time * 1000)
        return jsonify({"status": "success", "action": "seek", "time": new_time})
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
        return
    
    try:
        if params:
            url = f"{partner_url}/{command}/{params}"
        else:
            url = f"{partner_url}/{command}"
        requests.get(url, timeout=1)
    except requests.exceptions.RequestException as e:
        print(f"Failed to send command to partner: {command}. Error: {e}")

def main():
    global player, partner_url

    partner_url = input("Enter partner's URL: ").strip()

    server_thread = Thread(target=start_server)
    server_thread.daemon = True
    server_thread.start()

    file_path = input("Enter the full path to the video file: ").strip()

    if file_path.startswith('"') and file_path.endswith('"'):
        file_path = file_path[1:-1]

    if not os.path.exists(file_path):
        print("File does not exist. Please check the path and try again.")
        return

    
    instance = vlc.Instance("--quiet") 
    player = instance.media_player_new()
    media = instance.media_new(file_path)
    player.set_media(media)
    
    print(f"File loaded: {file_path}")
    
    while True:
        print("\nControls:")
        print("1. Pause")
        print("2. Play")
        print("3. Seek (forward/backward)")
        print("4. Stop")
        print("5. Exit")
        choice = input("Enter your choice: ")
        
        if choice == "1":
            send_command("pause")
            player.pause()
            print("Paused locally and sent pause command to partner.")
            
        elif choice == "2":
            send_command("play")
            player.play()
            print("Playing locally and sent play command to partner.")
            
        elif choice == "3":
            try:
                current_time = player.get_time() // 1000
                print(f"Current time: {current_time} seconds")
                seek_time = int(input("Enter seconds to seek (positive for forward, negative for backward): "))
                new_time = current_time + seek_time
                send_command("seek", seek_time)
                player.set_time(new_time * 1000)
                print(f"Seeked to: {new_time} seconds locally and sent seek command to partner.")
            except ValueError:
                print("Invalid input. Please enter a number.")
                
        elif choice == "4":
            send_command("stop")
            player.stop()
            print("Stopped locally and sent stop command to partner.")
            
        elif choice == "5":
            print("Exiting...")
            player.stop()
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()

import vlc
import os
from flask import Flask, jsonify
import requests
from threading import Thread
import time

app = Flask(__name__)
player = None
partner_url = None

# Routes for controlling playback
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
    app.run(host='0.0.0.0', port=80, threaded=True)

def send_command(command, params=None):
    if not partner_url:
        return
    
    try:
        if params:
            url = f"{partner_url}/{command}/{params}"
        else:
            url = f"{partner_url}/{command}"
        requests.get(url, timeout=1)
    except requests.exceptions.RequestException:
        print(f"Failed to send command to partner: {command}")

def main():
    global player, partner_url
    
    # Get partner's URL
    print("Enter partner's URL (e.g., https://2 if you're device A, https://1 if you're device B):")
    partner_url = input().strip()
    
    # Start server in a separate thread
    server_thread = Thread(target=start_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Initialize video player
    file_path = input("Enter the full path to the video file: ")
    
    if not os.path.exists(file_path):
        print("File does not exist. Please check the path and try again.")
        return
    
    player = vlc.MediaPlayer(file_path)
    print(f"Playing: {file_path}")
    
    while True:
        print("\nControls:")
        print("1. Pause")
        print("2. Play")
        print("3. Seek (forward/backward)")
        print("4. Stop")
        print("5. Exit")
        choice = input("Enter your choice: ")
        
        if choice == "1":
            player.pause()
            send_command("pause")
            print("Paused locally and sent pause command to partner.")
            
        elif choice == "2":
            player.play()
            send_command("play")
            print("Playing locally and sent play command to partner.")
            
        elif choice == "3":
            try:
                current_time = player.get_time() // 1000
                print(f"Current time: {current_time} seconds")
                seek_time = int(input("Enter seconds to seek (positive for forward, negative for backward): "))
                new_time = current_time + seek_time
                player.set_time(new_time * 1000)
                send_command("seek", seek_time)
                print(f"Seeked to: {new_time} seconds locally and sent seek command to partner.")
            except ValueError:
                print("Invalid input. Please enter a number.")
                
        elif choice == "4":
            player.stop()
            send_command("stop")
            print("Stopped locally and sent stop command to partner.")
            
        elif choice == "5":
            print("Exiting...")
            player.stop()
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
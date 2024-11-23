import subprocess
import time
from flask import Flask
from waitress import serve
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "Hello, the server is running!"

def start_server():
    """Start the Flask server."""
    serve(app, host='0.0.0.0', port=5000)

def forward_port():
    """Forward port 5000 using VS Code API."""
    try:
        # Run VS Code command for port forwarding
        subprocess.run(
            [
                "code", 
                "--executeCommand", 
                "remote.forwardPort",
                '{"port":5000,"onAutoForward":"openBrowser","label":"Public Flask Server"}'
            ],
            check=True,
        )
        print("Port 5000 forwarded successfully.")
    except subprocess.CalledProcessError as e:
        print("Failed to forward port 5000:", e)

if __name__ == "__main__":
    # Forward the port first
    forward_port()

    # Give some time for the port to be ready
    time.sleep(3)  # Adjust the sleep time if necessary

    # Start the Flask server
    print("Starting the Flask server...")
    Thread(target=start_server, daemon=True).start()

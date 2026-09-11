from flask import Flask, request, jsonify
from functools import wraps
import os
from lock_lights_serial_input import open_drawer, emUnlock, rgbOn

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    raise ValueError("No API_KEY environment variable set")

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        provided_key = request.headers.get('X-API-Key')
        if not provided_key or provided_key != API_KEY:
            return jsonify({"error": "Unauthorized - Invalid API Key"}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route("/status", methods=["GET"])
@require_api_key
def api_status():
    return jsonify({"status": "online"})

@app.route("/open_drawer", methods=["POST"])
@require_api_key
def api_open_drawer():
    data = request.json
    drawer_num = data.get("drawer")
    if drawer_num is None:
        return jsonify({"error": "No drawer number provided"}), 400

    open_drawer(drawer_num)
    return jsonify({"status": "success", "message": f"Drawer {drawer_num} opened"})

@app.route("/unlock", methods=["POST"])
@require_api_key
def api_unlock():
    emUnlock()
    return jsonify({"status": "success", "message": "Unlocked"})

@app.route("/light", methods=["POST"])
@require_api_key
def api_light():
    data = request.json
    box_num = data.get("box")
    if box_num is None:
        return jsonify({"error": "No box number provided"}), 400

    rgbOn(box_num)
    return jsonify({"status": "success", "message": f"Light turned on for box {box_num}"})

import signal
import sys

def cleanup_and_exit(sig, frame):
    print("Cleaning up before exit...")
    try:
        if 'ser' in globals() and ser.is_open:
            ser.close()
            print("Serial port closed.")
    except Exception as e:
        print(f"Error closing serial port: {e}")
    
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup_and_exit) 
signal.signal(signal.SIGTERM, cleanup_and_exit)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
"""Single maintained API. Deploy on loopback behind an HTTPS reverse proxy."""
import atexit
from functools import wraps
import hmac
import logging
import os
from flask import Flask, jsonify, request
try:
    from .lock_lights_serial_input import Controller, Data, box
except ImportError:
    from lock_lights_serial_input import Controller, Data, box

def create_app(controller=None, api_key=None):
    key = api_key or os.environ.get("MAS_API_KEY")
    if not key or len(key) < 32:
        raise ValueError("Set a newly generated MAS_API_KEY of at least 32 characters.")
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 4096
    device = controller if controller is not None else Controller()
    app.extensions["drawer_controller"] = device
    if controller is None:
        atexit.register(device.close)

    def reply(ok, message, status=200):
        return jsonify(ok=ok, protocol="MAS/1", message=message, physical_state="unmeasured"), status

    def authorized(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            supplied = request.headers.get("X-API-Key", "")
            if not hmac.compare_digest(supplied.encode(), key.encode()):
                return reply(False, "Unauthorized", 401)
            return function(*args, **kwargs)
        return wrapper

    def body(required=None):
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")
        allowed = {required} if required else set()
        if set(data) != allowed:
            raise ValueError(f"Expected fields: {', '.join(allowed) or 'none'}.")
        return box(data[required]) if required else None

    def execute(action, label):
        try:
            action()
            app.logger.info("Device command acknowledged: %s", label)
            return reply(True, f"{label}: firmware acknowledged. Physical state is not measured.")
        except ValueError as exc:
            return reply(False, str(exc), 400)
        except Exception:
            app.logger.exception("Device command failed: %s", label)
            return reply(False, "Device unavailable or acknowledgement failed. Do not retry uncertain access; reconcile.", 503)

    @app.errorhandler(ValueError)
    def invalid(exc):
        return reply(False, str(exc), 400)

    @app.errorhandler(413)
    def too_large(exc):
        return reply(False, "Request is too large.", 413)

    @app.get("/status")
    @authorized
    def status():
        return execute(device.status, "Protocol readiness checked")

    @app.post("/open_drawer")
    @authorized
    def open_drawer():
        number = body("drawer")
        return execute(lambda: device.open(number), f"Select compartment {number}")

    @app.post("/lock_drawer")
    @authorized
    def lock_drawer():
        body()
        return execute(device.lock_all, "Lock all")

    @app.post("/unlock_cabinet_lock")
    @authorized
    def unlock_cabinet():
        number = body("box")
        return execute(lambda: device.open(number), f"Select compartment {number}")

    @app.post("/lock_cabinet_lock")
    @authorized
    def lock_cabinet():
        number = body("box")
        return execute(lambda: device.command(Data(number + 4)), f"Lock compartment {number}")

    @app.post("/light")
    @authorized
    def light():
        number = body("box")
        return execute(lambda: device.command(Data(number + 10)), f"Light compartment {number}")

    @app.post("/unlock")
    @authorized
    def emergency():
        body()
        return reply(False, "Emergency all-compartment access is disabled until the hardware procedure is specified.", 409)

    return app

def main():
    from waitress import serve
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    try:
        serve(app, host="127.0.0.1", port=5000, threads=4)
    finally:
        app.extensions["drawer_controller"].close()

if __name__ == "__main__":
    main()

"""Loopback browser interface sharing the maintained SQLite workflows."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import date, timedelta
import io
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import webbrowser

from flask import Flask, jsonify, request, send_file
from werkzeug.exceptions import HTTPException
from .catalog import Catalog, identifier
from .hardware import Simulator, SerialHardware, HttpHardware
from .team_hardware import TeamSerialHardware
from .photos import cached, fetch_photo
from .store import Store
from .workflows import WorkflowService

ROOT = Path(__file__).resolve().parents[1]


def create_app(store, catalog, hardware):
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024
    service = WorkflowService(store, catalog, hardware)
    app.extensions["pharm"] = service
    token = secrets.token_urlsafe(32)
    photos = ThreadPoolExecutor(max_workers=1)
    app.extensions["photos"] = photos
    photo_jobs = {}
    image_dir = store.path.parent / "images"

    @app.before_request
    def local_requests():
        if request.host.split(":", 1)[0] not in ("localhost", "127.0.0.1"):
            return jsonify(ok=False, message="Use the local cabinet address."), 403
        if request.method != "GET":
            origin = request.headers.get("Origin")
            if (origin and origin != request.host_url.rstrip("/")) or not secrets.compare_digest(request.headers.get("X-Pharm-Token", ""), token):
                return jsonify(ok=False, message="Reload the cabinet page before continuing."), 403
            if request.path != "/api/catalog" and (request.content_length or 0) > 65536:
                return jsonify(ok=False, message="Request is too large."), 413

    @app.after_request
    def private_responses(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.errorhandler(ValueError)
    def bad_input(exc):
        return jsonify(ok=False, message=str(exc)), 409

    @app.errorhandler(HTTPException)
    def request_error(exc):
        return jsonify(ok=False, message=exc.description), exc.code

    def body():
        value = request.get_json()
        if not isinstance(value, dict):
            raise ValueError("Supply an object with the requested operation details.")
        types = {"operation": str, "scan": str, "kind": str, "reason": str,
                 "drawer": int, "count": int, "product": dict,
                 "placed": bool, "closed": bool, "secured": bool, "remaining_ids": list}
        if any(key not in types or type(item) is not types[key] for key, item in value.items()):
            raise ValueError("Invalid operation fields or field types.")
        if "remaining_ids" in value and any(not isinstance(i, str) for i in value["remaining_ids"]):
            raise ValueError("Select valid box records.")
        return value

    @app.get("/cabinet.css")
    def style():
        return send_file(ROOT / "UI/web/cabinet.css")

    @app.get("/")
    def home():
        page = (ROOT / "UI/web/index.html").read_text(encoding="utf-8")
        return page.replace("__PHARM_TOKEN__", token)

    @app.get("/api/state")
    def state():
        result = []
        today = date.today()
        for drawer in store.compartments():
            product = drawer["product"]
            expiry = product.get("expiry_date")
            photo = cached(image_dir, product["ndc"]) if product else None
            if not photo and product:
                photo = cached(ROOT / "UI/images", product["ndc"])
            result.append({**drawer, "expiring": bool(expiry and date.fromisoformat(expiry) <= today + timedelta(days=31)),
                           "photo": f"/images/{photo.name}" if photo else None})
        active = store.active()
        choices = store.reconciliation_items(active["id"]) if active else []
        return jsonify(ok=True, drawers=result, active=active, choices=choices, mode=hardware.mode,
                       open_mode=getattr(hardware, "open_drawers", [hardware.selected] if getattr(hardware, "selected", None) else []),
                       simulation=isinstance(hardware, Simulator), catalog=service.catalog.warning,
                       photo_jobs={k: "complete" if f.done() and not f.exception() else "failed" if f.done() else "loading" for k, f in photo_jobs.items()})

    @app.get("/api/status")
    def status():
        with service.lock:
            result = hardware.status()
            selected = getattr(hardware, "selected", None)
            return jsonify(ok=result.ok, message=result.message,
                           open_mode=getattr(hardware, "open_drawers", [selected] if selected else []),
                           output_unlocked=getattr(hardware, "output_unlocked", []), physical_closure="unmeasured")

    @app.post("/api/preview")
    def preview():
        return jsonify(ok=True, **service.preview(body().get("scan", "")))

    @app.post("/api/start")
    def start():
        data = body()
        op = service.start(data.get("kind"), data.get("drawer"), data.get("count", 0), data.get("product"), data.get("scan", ""), data.get("reason", ""))
        return jsonify(ok=True, operation=op)

    @app.post("/api/find")
    def find():
        scan = body().get("scan", "")
        matches = [d["id"] for d in store.compartments() if d["product"] and service.catalog.matches(scan, d["product"]["ndc"])]
        if not matches:
            raise ValueError("This package is not stored in any drawer.")
        return jsonify(ok=True, drawers=matches)

    @app.post("/api/secure")
    def secure():
        service.secure(body().get("operation"))
        return jsonify(ok=True)

    @app.post("/api/verify")
    def verify():
        data = body()
        return jsonify(ok=True, operation=service.verify(data.get("operation"), data.get("scan", "")))

    @app.post("/api/reopen")
    def reopen():
        service.reopen(body().get("operation"))
        return jsonify(ok=True)

    @app.post("/api/add")
    def add():
        data = body()
        return jsonify(ok=True, operation=service.add(data.get("operation"), data.get("product", {}), data.get("scan", "")))

    @app.post("/api/finish")
    def finish():
        data = body()
        result = service.finish(data.get("operation"), data.get("placed"), data.get("closed"))
        return jsonify(ok=True, lock_ok=result.ok, lock_message=result.message)

    @app.post("/api/cancel")
    def cancel():
        data = body()
        service.cancel(data.get("operation"), data.get("reason", "Cancelled"))
        return jsonify(ok=True)

    @app.post("/api/reconcile")
    def reconcile():
        data = body()
        result = service.reconcile(data.get("operation"), data.get("count"), data.get("reason", ""), data.get("closed"), data.get("remaining_ids"))
        return jsonify(ok=True, lock_ok=result.ok, lock_message=result.message)

    @app.get("/api/audit")
    def audit():
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=["id", "time", "operator", "operation", "action", "detail"])
        writer.writeheader()
        for row in store.audit():
            writer.writerow({k: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r")) else v for k, v in row.items()})
        return send_file(io.BytesIO(output.getvalue().encode("utf-8")), mimetype="text/csv", as_attachment=True, download_name="cabinet-audit.csv")

    @app.get("/api/backup")
    def backup():
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.sqlite3"
            store.backup(path)
            content = path.read_bytes()
        return send_file(io.BytesIO(content), mimetype="application/octet-stream", as_attachment=True, download_name="cabinet-backup.sqlite3")

    @app.post("/api/catalog")
    def choose_catalog():
        if store.active():
            raise ValueError("Complete or reconcile the current operation before changing catalogs.")
        upload = request.files.get("catalog")
        if not upload:
            raise ValueError("Choose a compatible JSON package catalog.")
        target = store.path.parent / ("catalog-" + secrets.token_hex(8) + ".json")
        upload.save(target)
        candidate = Catalog(target)
        if candidate.warning:
            target.unlink()
            raise ValueError(candidate.warning)
        with service.lock, store.transaction() as db:
            if db.execute("SELECT 1 FROM operations WHERE state IN ('pending','access','reconciliation')").fetchone():
                target.unlink()
                raise ValueError("Complete or reconcile the current operation before changing catalogs.")
            temporary = store.path.parent / "catalog-path.tmp"
            temporary.write_text(json.dumps(str(target.resolve())), encoding="utf-8")
            temporary.replace(store.path.parent / "catalog-path.json")
            service.catalog = candidate
        return jsonify(ok=True)

    @app.get("/images/<filename>")
    def image(filename):
        path = Path(filename)
        if path.name != filename or path.suffix not in (".jpg", ".png", ".gif"):
            return jsonify(ok=False), 404
        try:
            key = identifier(path.stem)
        except ValueError:
            return jsonify(ok=False), 404
        for directory in (image_dir, ROOT / "UI/images"):
            photo = cached(directory, key)
            if photo and photo.name == filename:
                return send_file(photo)
        return jsonify(ok=False), 404

    @app.post("/api/photo/<int:number>")
    def photo(number):
        if number not in range(1, 5):
            raise ValueError("Choose drawer 1 through 4.")
        product = store.compartments()[number - 1]["product"]
        if not product:
            raise ValueError("Load a package before requesting its photo.")
        key = identifier(product["ndc"])
        if key not in photo_jobs or photo_jobs[key].done():
            photo_jobs[key] = photos.submit(fetch_photo, image_dir, product["ndc"])
        return jsonify(ok=True, message="Photo lookup started. Inventory does not depend on its result.")

    return app


def main(argv=None):
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--usb-port")
    modes.add_argument("--team-usb-port")
    modes.add_argument("--hardware-bench", action="store_true")
    modes.add_argument("--no-hardware", action="store_true", help="Explicit simulation (also the default)")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args(argv)
    mode = "bench" if args.usb_port or args.team_usb_port or args.hardware_bench else "simulation"
    directory = args.data_dir or Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share"))) / "EPICS-Pharm" / mode
    catalog_path = args.catalog or ROOT / "UI/db.json"
    if not args.catalog:
        try:
            saved = json.loads((directory / "catalog-path.json").read_text(encoding="utf-8"))
            if isinstance(saved, str) and saved.strip():
                catalog_path = Path(saved)
        except (OSError, ValueError):
            pass
    hardware = SerialHardware(args.usb_port) if args.usb_port else TeamSerialHardware(args.team_usb_port) if args.team_usb_port else HttpHardware(os.environ.get("MAS_API_URL", ""), os.environ.get("MAS_API_KEY", ""), os.environ.get("MAS_CA_FILE")) if args.hardware_bench else Simulator()
    app = create_app(Store(directory / "inventory.sqlite3"), Catalog(catalog_path), hardware)
    try:
        print(f"Open http://127.0.0.1:{args.port} in your browser. Mode: {hardware.mode}", flush=True)
        if args.open_browser:
            launch_browser = threading.Timer(1, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}"))
            launch_browser.daemon = True
            launch_browser.start()
        app.run(host="127.0.0.1", port=args.port, threaded=True, use_reloader=False)
    finally:
        app.extensions["photos"].shutdown(wait=False, cancel_futures=True)
        hardware.close()


if __name__ == "__main__":
    main()

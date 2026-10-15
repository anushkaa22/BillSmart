"""BillSmart desktop entry point.

Starts the Flask app on waitress in a background thread and opens it in a
native window via pywebview (Edge WebView2 on Windows). Falls back to the
system browser if pywebview/WebView2 is unavailable.
"""
import os
import atexit
import socket
import threading
import time
import urllib.request
import webbrowser

os.environ.setdefault("BILLSMART_PORTABLE", "installed")

from app import APP_NAME, APP_VERSION, DATA_DIR, app, find_free_port

SINGLE_INSTANCE_PORT = int(os.environ.get("BILLSMART_LOCK_PORT", "51229"))
HOST = "127.0.0.1"
PORT = find_free_port() or 5000
URL = f"http://{HOST}:{PORT}"

_lock_socket = None


def _port_file():
    return DATA_DIR / "running-port.txt"


def _acquire_single_instance():
    global _lock_socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((HOST, SINGLE_INSTANCE_PORT))
    except OSError:
        return False
    _lock_socket = sock
    try:
        _port_file().write_text(str(PORT))
    except OSError:
        pass
    atexit.register(_release_single_instance)
    return True


def _release_single_instance():
    try:
        _port_file().unlink(missing_ok=True)
    except OSError:
        pass


def _already_running_url():
    try:
        port = int(_port_file().read_text().strip())
        return f"http://{HOST}:{port}"
    except (OSError, ValueError):
        return None


def _wait_for_server(timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(URL + "/healthz", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def _run_server():
    try:
        from waitress import serve
        serve(app, host=HOST, port=PORT, threads=8)
    except ImportError:
        app.run(host=HOST, port=PORT, debug=False, use_reloader=False)


def main():
    if not _acquire_single_instance():
        existing = _already_running_url()
        if existing:
            try:
                webbrowser.open(existing)
            except Exception:
                pass
        print(f"{APP_NAME} is already running.")
        raise SystemExit(0)

    log_file = DATA_DIR / "billsmart.log"
    thread = threading.Thread(target=_run_server, daemon=True)
    thread.start()

    if not _wait_for_server():
        with open(log_file, "a", encoding="utf-8") as fh:
            fh.write("Server failed to start.\n")
        raise SystemExit("Could not start the BillSmart server.")

    try:
        import webview
        window = webview.create_window(
            f"{APP_NAME} {APP_VERSION}",
            URL,
            maximized=True,
            min_size=(1024, 700),
        )
        webview.start()
    except Exception as exc:
        with open(log_file, "a", encoding="utf-8") as fh:
            fh.write(f"webview unavailable ({exc}); opened browser instead.\n")
        webbrowser.open(URL)
        thread.join()


if __name__ == "__main__":
    main()

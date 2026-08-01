from __future__ import annotations

import argparse
import base64
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import struct
import subprocess
import tempfile
from threading import Thread
import time
from urllib.parse import urlparse
from urllib.request import urlopen


class _QuietModuleHandler(SimpleHTTPRequestHandler):
    def guess_type(self, path: str) -> str:
        if path.endswith(".tsx"):
            return "text/javascript"
        return super().guess_type(path)

    def log_message(self, format: str, *args: object) -> None:
        pass


def _browser(explicit: str | None) -> Path:
    supplied = explicit or os.environ.get("E2E_BROWSER")
    if supplied:
        candidate = Path(supplied).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
        raise RuntimeError(
            "E2E_BROWSER_UNAVAILABLE: --browser/E2E_BROWSER must name an executable Chrome or Chromium binary"
        )
    for name in ("google-chrome", "chromium", "chromium-browser"):
        discovered = shutil.which(name)
        if discovered:
            return Path(discovered)
    applications = Path("/Applications")
    for relative in (
        "Google Chrome.app/Contents/MacOS/Google Chrome",
        "Chromium.app/Contents/MacOS/Chromium",
        "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ):
        candidate = applications / relative
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise RuntimeError(
        "E2E_BROWSER_UNAVAILABLE: install Chrome/Chromium or pass --browser / E2E_BROWSER"
    )


def _read_exact(connection: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise RuntimeError("E2E_CDP_FAILURE: unexpected WebSocket EOF")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class _WebSocket:
    def __init__(self, endpoint: str, timeout: float = 5.0) -> None:
        parsed = urlparse(endpoint)
        if parsed.scheme != "ws" or parsed.port is None:
            raise RuntimeError("E2E_CDP_FAILURE: invalid DevTools WebSocket endpoint")
        self.connection = socket.create_connection(("127.0.0.1", parsed.port), timeout)
        self.connection.settimeout(timeout)
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        request = (
            f"GET {parsed.path or '/'}{('?' + parsed.query) if parsed.query else ''} HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{parsed.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.connection.sendall(request.encode("ascii"))
        response = bytearray()
        while b"\r\n\r\n" not in response:
            response.extend(self.connection.recv(4096))
            if len(response) > 65536:
                raise RuntimeError("E2E_CDP_FAILURE: oversized WebSocket handshake")
        header = bytes(response).split(b"\r\n\r\n", 1)[0]
        expected = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        )
        if not header.startswith(b"HTTP/1.1 101") or expected.lower() not in header.lower():
            raise RuntimeError("E2E_CDP_FAILURE: DevTools WebSocket handshake was rejected")

    def close(self) -> None:
        try:
            self._send_frame(0x8, b"")
        except OSError:
            pass
        self.connection.close()

    def send_json(self, value: dict[str, object]) -> None:
        self._send_frame(0x1, json.dumps(value, separators=(",", ":")).encode("utf-8"))

    def receive_json(self) -> dict[str, object]:
        fragments = bytearray()
        while True:
            first, second = _read_exact(self.connection, 2)
            opcode = first & 0x0F
            final = bool(first & 0x80)
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", _read_exact(self.connection, 2))[0]
            elif length == 127:
                length = struct.unpack("!Q", _read_exact(self.connection, 8))[0]
            mask = _read_exact(self.connection, 4) if masked else b""
            payload = _read_exact(self.connection, length)
            if masked:
                payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
            if opcode == 0x8:
                raise RuntimeError("E2E_CDP_FAILURE: DevTools WebSocket closed unexpectedly")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode in {0x1, 0x0}:
                fragments.extend(payload)
                if final:
                    try:
                        value = json.loads(fragments.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as error:
                        raise RuntimeError("E2E_CDP_FAILURE: invalid DevTools JSON") from error
                    if not isinstance(value, dict):
                        raise RuntimeError("E2E_CDP_FAILURE: DevTools message was not an object")
                    return value

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        mask = secrets.token_bytes(4)
        length = len(payload)
        header = bytearray([0x80 | opcode])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        self.connection.sendall(bytes(header) + mask + masked)


class _CDP:
    def __init__(self, endpoint: str) -> None:
        self.websocket = _WebSocket(endpoint)
        self.next_id = 1

    def close(self) -> None:
        self.websocket.close()

    def command(self, method: str, params: dict[str, object] | None = None) -> dict[str, object]:
        message_id = self.next_id
        self.next_id += 1
        self.websocket.send_json(
            {"id": message_id, "method": method, "params": params or {}}
        )
        while True:
            message = self.websocket.receive_json()
            if message.get("id") != message_id:
                continue
            if "error" in message:
                raise RuntimeError(f"E2E_CDP_FAILURE: {method} returned {message['error']!r}")
            result = message.get("result", {})
            if not isinstance(result, dict):
                raise RuntimeError(f"E2E_CDP_FAILURE: {method} returned invalid result")
            return result


OBSERVE = r"""
(() => {
  const root = document.getElementById('panel-root');
  const status = root && root.querySelector('[role="status"]');
  const button = root && root.querySelector('button');
  const style = status && getComputedStyle(status);
  const rect = status && status.getBoundingClientRect();
  const buttonRect = button && button.getBoundingClientRect();
  return {
    importState: document.documentElement.dataset.import || 'pending',
    importError: document.documentElement.dataset.importError || '',
    status: status ? status.innerText : null,
    pressed: button ? button.getAttribute('aria-pressed') : null,
    visible: Boolean(status && style && rect && rect.width > 0 && rect.height > 0
      && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0'),
    button: buttonRect ? {
      x: buttonRect.x + buttonRect.width / 2,
      y: buttonRect.y + buttonRect.height / 2,
      width: buttonRect.width,
      height: buttonRect.height
    } : null
  };
})()
"""


def _evaluate(cdp: _CDP) -> dict[str, object]:
    result = cdp.command(
        "Runtime.evaluate",
        {"expression": OBSERVE, "returnByValue": True, "awaitPromise": True},
    )
    remote = result.get("result", {})
    if not isinstance(remote, dict) or remote.get("type") != "object":
        raise RuntimeError("E2E_CDP_FAILURE: DOM observation did not return an object")
    value = remote.get("value")
    if not isinstance(value, dict):
        raise RuntimeError("E2E_CDP_FAILURE: DOM observation had no value")
    return value


def _poll(cdp: _CDP, *, status: str, pressed: str, timeout: float = 8.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    last: dict[str, object] = {}
    while time.monotonic() < deadline:
        last = _evaluate(cdp)
        if last.get("importState") == "error":
            raise RuntimeError(f"E2E_IMPORT_ERROR: {last.get('importError') or 'module import failed'}")
        if (
            last.get("importState") == "complete"
            and last.get("status") == status
            and last.get("pressed") == pressed
            and last.get("visible") is True
        ):
            return last
        time.sleep(0.05)
    raise RuntimeError(
        f"E2E_BEHAVIOR_MISMATCH: rendered DOM did not reach status={status!r}, "
        f"aria-pressed={pressed!r}, visible=true; last={last!r}"
    )


def _click(cdp: _CDP, button: object) -> None:
    if not isinstance(button, dict):
        raise RuntimeError("E2E_BEHAVIOR_MISMATCH: rendered button is missing")
    x, y = button.get("x"), button.get("y")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        raise RuntimeError("E2E_BEHAVIOR_MISMATCH: rendered button has no clickable center")
    for event_type, buttons in (("mouseMoved", 0), ("mousePressed", 1), ("mouseReleased", 0)):
        params: dict[str, object] = {
            "type": event_type,
            "x": x,
            "y": y,
            "button": "left",
            "buttons": buttons,
        }
        if event_type != "mouseMoved":
            params["clickCount"] = 1
        cdp.command("Input.dispatchMouseEvent", params)


def _wait_devtools(profile: Path, process: subprocess.Popen[str]) -> tuple[int, str]:
    active = profile / "DevToolsActivePort"
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"E2E_BROWSER_FAILURE: browser exited {process.returncode} before DevTools became ready"
            )
        if active.is_file():
            lines = active.read_text(encoding="utf-8").splitlines()
            if len(lines) >= 2 and lines[0].isdigit():
                return int(lines[0]), lines[1]
        time.sleep(0.05)
    raise RuntimeError("E2E_BROWSER_FAILURE: bounded DevTools startup timed out")


def _page_endpoint(port: int) -> str:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1) as response:
                targets = json.loads(response.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError):
            time.sleep(0.05)
            continue
        for target in targets if isinstance(targets, list) else []:
            if isinstance(target, dict) and target.get("type") == "page":
                endpoint = target.get("webSocketDebuggerUrl")
                if isinstance(endpoint, str):
                    return endpoint
        time.sleep(0.05)
    raise RuntimeError("E2E_CDP_FAILURE: no page target became available")


def _cleanup(process: subprocess.Popen[str], browser_cdp: _CDP | None) -> None:
    if browser_cdp is not None:
        try:
            browser_cdp.command("Browser.close")
        except (OSError, RuntimeError, socket.timeout):
            pass
    try:
        process.wait(timeout=3)
        return
    except subprocess.TimeoutExpired:
        pass
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3)


def _exercise(browser: Path, url: str) -> str:
    with tempfile.TemporaryDirectory(prefix="moondex-panel-profile-") as temporary:
        profile = Path(temporary)
        log = profile / "browser.log"
        with log.open("w", encoding="utf-8") as browser_log:
            process = subprocess.Popen(
                [
                    str(browser),
                    "--headless=new",
                    "--disable-gpu",
                    "--disable-background-networking",
                    "--disable-component-update",
                    "--disable-default-apps",
                    "--disable-extensions",
                    "--disable-sync",
                    "--metrics-recording-only",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--remote-debugging-address=127.0.0.1",
                    "--remote-debugging-port=0",
                    f"--user-data-dir={profile}",
                    "about:blank",
                ],
                stdout=browser_log,
                stderr=browser_log,
                text=True,
                start_new_session=True,
            )
            browser_cdp: _CDP | None = None
            page_cdp: _CDP | None = None
            try:
                port, browser_path = _wait_devtools(profile, process)
                browser_cdp = _CDP(f"ws://127.0.0.1:{port}{browser_path}")
                page_cdp = _CDP(_page_endpoint(port))
                page_cdp.command("Page.enable")
                page_cdp.command("Runtime.enable")
                page_cdp.command("Page.navigate", {"url": url})
                initial = _poll(page_cdp, status="Ready", pressed="false")
                _click(page_cdp, initial.get("button"))
                _poll(page_cdp, status="Complete", pressed="true")
                version = browser_cdp.command("Browser.getVersion").get("product")
                if not isinstance(version, str) or not version:
                    raise RuntimeError("E2E_CDP_FAILURE: browser version was unavailable")
                return version
            finally:
                if page_cdp is not None:
                    page_cdp.close()
                _cleanup(process, browser_cdp)
                if browser_cdp is not None:
                    browser_cdp.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Render and exercise the consumer panel through Chrome CDP.")
    parser.add_argument("--browser")
    args = parser.parse_args()
    root = Path.cwd().resolve(strict=True)
    browser = _browser(args.browser)
    handler = lambda *values, **options: _QuietModuleHandler(
        *values, directory=str(root), **options
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/tests/panel_runner.html"
        version = _exercise(browser, url)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    print(f"rendered panel E2E passed with {version}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, socket.timeout, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error))

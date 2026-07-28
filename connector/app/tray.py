"""Windows system-tray companion for the ONEVO connector service."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import requests

from .instance_lock import InstanceLock
from .paths import default_state_dir, install_dir


SERVICE_NAME = "ONEVOConnector"
DEFAULT_ADMIN_URL = "http://localhost:8099/"
HEALTH_URL = "http://127.0.0.1:8099/health"
TRAY_LOCK = "tray.lock"
TRAY_EXIT_SIGNAL = "tray.exit"
STARTUP_VALUE = "ONEVO Connector Tray"


def _subprocess_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def _tray_asset() -> Path:
    candidates = []
    bundle = getattr(sys, "_MEIPASS", "")
    if bundle:
        candidates.append(Path(bundle) / "assets" / "onevo.ico")
    candidates.extend([
        install_dir() / "assets" / "onevo.ico",
        install_dir() / "installer" / "assets" / "onevo.ico",
    ])
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("ONEVO tray icon is missing")


def _service_wrapper() -> Path:
    return install_dir() / "onevo-connector-service.exe"


def service_status() -> str:
    """Return running, starting, stopped, missing, or error."""
    if os.name != "nt":
        return "missing"
    result = subprocess.run(
        ["sc.exe", "query", SERVICE_NAME],
        capture_output=True,
        text=True,
        creationflags=_subprocess_flags(),
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}".upper()
    if "1060" in output or "DOES NOT EXIST" in output:
        return "missing"
    if "RUNNING" in output:
        return "running"
    if "START_PENDING" in output or "STOP_PENDING" in output:
        return "starting"
    if "STOPPED" in output:
        return "stopped"
    return "error"


def service_action(action: str) -> bool:
    wrapper = _service_wrapper()
    if not wrapper.is_file():
        return False
    result = subprocess.run(
        [str(wrapper), action],
        cwd=str(wrapper.parent),
        capture_output=True,
        creationflags=_subprocess_flags(),
        check=False,
    )
    return result.returncode == 0


def health_ready(timeout: float = 1.5) -> bool:
    try:
        response = requests.get(HEALTH_URL, timeout=timeout)
        return response.ok and bool(response.json().get("ok"))
    except (requests.RequestException, ValueError):
        return False


def wait_for_health(max_wait: float = 30.0, interval: float = 1.0) -> bool:
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        if health_ready():
            return True
        time.sleep(interval)
    return health_ready()


def open_admin(max_wait: float = 30.0) -> bool:
    """Ensure the service is available, then open the local dashboard."""
    if not health_ready():
        if service_status() == "stopped":
            service_action("start")
        if not wait_for_health(max_wait=max_wait):
            return False
    return bool(webbrowser.open(DEFAULT_ADMIN_URL))


def request_tray_exit() -> int:
    state_dir = Path(default_state_dir())
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / TRAY_EXIT_SIGNAL).touch()
    return 0


def startup_enabled() -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
        ) as key:
            value, _ = winreg.QueryValueEx(key, STARTUP_VALUE)
        return "--tray" in str(value)
    except OSError:
        return False


def set_startup(enabled: bool) -> bool:
    if os.name != "nt":
        return False
    import winreg
    try:
        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
        ) as key:
            if enabled:
                command = f'"{sys.executable}" --tray'
                winreg.SetValueEx(key, STARTUP_VALUE, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, STARTUP_VALUE)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def uninstall_tray() -> int:
    request_tray_exit()
    set_startup(False)
    # Wait until the running tray process consumes the signal and releases its
    # lock. Otherwise the uninstaller can delete the signal directory first,
    # leaving a stale notification icon alive until the next Windows login.
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        probe = InstanceLock(str(default_state_dir()), TRAY_LOCK)
        if probe.acquire():
            probe.release()
            break
        time.sleep(0.2)
    return 0


class TrayApplication:
    def __init__(self):
        self.state_dir = Path(default_state_dir())
        self.lock = InstanceLock(str(self.state_dir), TRAY_LOCK)
        self.exit_signal = self.state_dir / TRAY_EXIT_SIGNAL
        self.stop_event = threading.Event()
        self.status = "Starting"
        self.icon = None
        self._last_notice = ""

    def _refresh_status(self) -> None:
        service = service_status()
        if service == "running":
            self.status = "Running" if health_ready() else "Starting"
        elif service == "starting":
            self.status = "Starting"
        elif service == "stopped":
            self.status = "Stopped"
        elif service == "missing":
            self.status = "Not installed"
        else:
            self.status = "Error"
        if self.icon is not None:
            self.icon.title = f"ONEVO Connector — {self.status}"
            self.icon.update_menu()

    def _status_loop(self) -> None:
        while not self.stop_event.wait(5):
            if self.exit_signal.exists():
                try:
                    self.exit_signal.unlink()
                except OSError:
                    pass
                self.stop()
                return
            self._refresh_status()

    def _open_dashboard(self, _icon=None, _item=None) -> None:
        def worker():
            if not open_admin():
                self._notify(
                    "Local dashboard is not ready. Check the ONEVO Connector service."
                )
            self._refresh_status()
        threading.Thread(target=worker, daemon=True).start()

    def _restart_service(self, _icon=None, _item=None) -> None:
        def worker():
            self.status = "Starting"
            if self.icon is not None:
                self.icon.update_menu()
            service_action("stop")
            time.sleep(1)
            if service_action("start") and wait_for_health():
                self._notify("ONEVO Connector restarted successfully.")
            else:
                self._notify("ONEVO Connector could not be restarted.")
            self._refresh_status()
        threading.Thread(target=worker, daemon=True).start()

    def _toggle_startup(self, _icon=None, _item=None) -> None:
        if not set_startup(not startup_enabled()):
            self._notify("Could not update the Start with Windows setting.")
        if self.icon is not None:
            self.icon.update_menu()

    def _notify(self, message: str) -> None:
        if self.icon is not None and message != self._last_notice:
            self._last_notice = message
            try:
                self.icon.notify(message, "ONEVO Connector")
            except Exception:
                pass

    def stop(self, _icon=None, _item=None) -> None:
        self.stop_event.set()
        if self.icon is not None:
            self.icon.stop()

    def run(self) -> int:
        if os.name != "nt":
            return 2
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if not self.lock.acquire():
            return 0
        try:
            if self.exit_signal.exists():
                self.exit_signal.unlink()
            set_startup(True)
            from PIL import Image
            import pystray

            image = Image.open(_tray_asset()).convert("RGBA")
            menu = pystray.Menu(
                pystray.MenuItem(
                    lambda _item: f"Status: {self.status}",
                    None,
                    enabled=False,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "Open Local Dashboard",
                    self._open_dashboard,
                    default=True,
                ),
                pystray.MenuItem("Restart Connector", self._restart_service),
                pystray.MenuItem("Refresh Status", lambda *_: self._refresh_status()),
                pystray.MenuItem(
                    "Start with Windows",
                    self._toggle_startup,
                    checked=lambda _item: startup_enabled(),
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit Tray", self.stop),
            )
            self.icon = pystray.Icon(
                "ONEVOConnectorTray",
                image,
                "ONEVO Connector — Starting",
                menu,
            )
            self._refresh_status()
            threading.Thread(target=self._status_loop, daemon=True).start()
            self.icon.run()
            return 0
        finally:
            self.stop_event.set()
            self.lock.release()


def run_tray() -> int:
    return TrayApplication().run()

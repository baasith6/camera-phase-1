"""Windows system-tray companion for the ONEVO connector service."""
from __future__ import annotations

import os
import hashlib
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .baked_config import BAKED_BACKEND_URL
from .instance_lock import InstanceLock
from .paths import default_state_dir, install_dir, pause_marker_path


SERVICE_NAME = "ONEVOConnector"
DEFAULT_ADMIN_URL = "http://localhost:8099/"
HEALTH_URL = "http://127.0.0.1:8099/health"
TRAY_LOCK = "tray.lock"
TRAY_EXIT_SIGNAL = "tray.exit"
STARTUP_VALUE = "ONEVO Connector Tray"
CURRENT_VERSION = "1.1.18"
UPDATE_MANIFEST_URL = os.getenv(
    "CONNECTOR_UPDATE_MANIFEST_URL",
    f"{BAKED_BACKEND_URL.rstrip('/')}/api/connectors/updates/latest",
)
UPDATE_CHECK_SECONDS = 6 * 60 * 60
UPDATE_PROMPT_FILE = "update-prompted-version.txt"


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


def set_service_auto_start(enabled: bool) -> bool:
    if os.name != "nt":
        return False
    result = subprocess.run(
        [
            "sc.exe",
            "config",
            SERVICE_NAME,
            "start=",
            "auto" if enabled else "demand",
        ],
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


def wait_for_health(max_wait: float = 60.0, interval: float = 1.0) -> bool:
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        if health_ready():
            return True
        time.sleep(interval)
    return health_ready()


def open_admin(max_wait: float = 60.0, url: str = DEFAULT_ADMIN_URL) -> bool:
    """Ensure the service is available, then open the local dashboard."""
    if not health_ready():
        status = service_status()
        if pause_marker_path().exists() or status == "missing":
            if not request_resume_monitoring():
                return False
        elif status == "stopped":
            if not service_action("start"):
                return False
        if not wait_for_health(max_wait=max_wait):
            return False
    # The local page elects one active tab before subscribing to live video.
    return bool(webbrowser.open(url))


def resume_monitoring(max_wait: float = 30.0) -> bool:
    """Clear persistent pause, repair the service if needed, then start it."""
    try:
        pause_marker_path().unlink(missing_ok=True)
        from .store import LocalStore
        local_store = LocalStore(str(default_state_dir()))
        local_store.set_bool_setting("monitoring_paused", False)
        local_store.close()
    except Exception:
        return False
    set_service_auto_start(True)
    status = service_status()
    if status == "running":
        return health_ready()
    if status == "missing" and not service_action("install"):
        return False
    return service_action("start") and wait_for_health(max_wait=max_wait)


def request_resume_monitoring() -> bool:
    """Ask Windows to run the service-resume helper with administrator rights."""
    if os.name != "nt":
        return False
    import ctypes
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        "--start-monitoring",
        str(install_dir()),
        0,
    )
    return result > 32


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
        self.update_available = False
        self.latest_version = ""
        self.update_metadata: dict = {}
        self.update_busy = False
        self._last_update_check = 0.0

    def _prompted_update_version(self) -> str:
        try:
            return (self.state_dir / UPDATE_PROMPT_FILE).read_text(
                encoding="utf-8"
            ).strip()
        except OSError:
            return ""

    def _mark_update_prompted(self, version: str) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / UPDATE_PROMPT_FILE).write_text(
            version, encoding="utf-8"
        )

    def _prompt_for_update(self, version: str) -> None:
        """Show one non-blocking toast; the tray menu keeps the deferred action."""
        if self._prompted_update_version() == version:
            return
        self._mark_update_prompted(version)
        self._notify(
            f"Version {version} is available. Select “Update available” in the tray when ready."
        )

    @staticmethod
    def _version_tuple(value: str) -> tuple[int, ...]:
        parts = []
        for part in value.split("."):
            digits = "".join(ch for ch in part if ch.isdigit())
            parts.append(int(digits or 0))
        return tuple((parts + [0, 0, 0, 0])[:4])

    def _check_updates(self, notify: bool = True) -> None:
        try:
            response = requests.get(UPDATE_MANIFEST_URL, timeout=15)
            response.raise_for_status()
            metadata = response.json()
            latest = str(metadata.get("version") or "").strip()
            available = bool(latest) and (
                self._version_tuple(latest) > self._version_tuple(CURRENT_VERSION)
            )
            newly_available = available and latest != self.latest_version
            self.update_metadata = metadata if available else {}
            self.latest_version = latest if available else ""
            self.update_available = available
            self._last_update_check = time.monotonic()
            if newly_available and notify and self.icon is not None:
                self._prompt_for_update(latest)
        except (requests.RequestException, ValueError, TypeError):
            self._last_update_check = time.monotonic()
        if self.icon is not None:
            self.icon.update_menu()

    def _install_update(self, _icon=None, _item=None) -> None:
        if self.update_busy or not self.update_available:
            return

        def worker():
            self.update_busy = True
            if self.icon is not None:
                self.icon.update_menu()
            try:
                metadata = self.update_metadata
                download_url = str(metadata.get("downloadUrl") or "").strip()
                expected_hash = str(metadata.get("sha256") or "").strip().lower()
                expected_size = int(metadata.get("sizeBytes") or 0)
                manifest_origin = urlsplit(UPDATE_MANIFEST_URL)
                download_origin = urlsplit(download_url)
                same_backend = (
                    manifest_origin.scheme == download_origin.scheme
                    and manifest_origin.netloc == download_origin.netloc
                )
                if download_origin.scheme != "https" and not (
                    download_origin.scheme == "http" and same_backend
                ):
                    raise RuntimeError("The update URL is not from the ONEVO backend.")
                update_dir = self.state_dir.parent / "updates"
                update_dir.mkdir(parents=True, exist_ok=True)
                target = update_dir / f"ONEVO-Connector-Update-{self.latest_version}.exe"
                partial = target.with_suffix(".exe.partial")
                digest = hashlib.sha256()
                received = 0
                self._notify(f"Downloading ONEVO Connector {self.latest_version}...")
                with requests.get(download_url, stream=True, timeout=(15, 120)) as response:
                    response.raise_for_status()
                    with partial.open("wb") as output:
                        for chunk in response.iter_content(1024 * 1024):
                            if not chunk:
                                continue
                            output.write(chunk)
                            digest.update(chunk)
                            received += len(chunk)
                if expected_size and received != expected_size:
                    raise RuntimeError("Downloaded update size does not match the release.")
                if not expected_hash or digest.hexdigest().lower() != expected_hash:
                    raise RuntimeError("Downloaded update failed SHA-256 verification.")
                partial.replace(target)
                self._notify(f"Installing ONEVO Connector {self.latest_version}...")
                if os.name != "nt":
                    raise RuntimeError("Connector updates are supported on Windows only.")
                import ctypes
                result = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    str(target),
                    "/UPDATE /SILENT /NORESTART",
                    str(target.parent),
                    0,
                )
                if result <= 32:
                    raise RuntimeError("Windows did not start the update installer.")
                self.stop()
            except Exception as exc:  # noqa: BLE001
                self._notify(f"Update failed: {exc}")
                self.update_busy = False
                if self.icon is not None:
                    self.icon.update_menu()

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_status(self) -> None:
        service = service_status()
        if service == "running":
            if not health_ready():
                self.status = "Starting"
            else:
                try:
                    local_status = requests.get(
                        f"{DEFAULT_ADMIN_URL}status", timeout=1.5
                    ).json()
                    self.status = (
                        "Stopped" if local_status.get("capturePaused") else "Running"
                    )
                except (requests.RequestException, ValueError):
                    self.status = "Starting"
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
            if time.monotonic() - self._last_update_check >= UPDATE_CHECK_SECONDS:
                self._check_updates()

    def _open_dashboard(self, _icon=None, _item=None) -> None:
        def worker():
            if not open_admin():
                self._notify(
                    "Local dashboard is not ready. Check the ONEVO Connector service."
                )
            self._refresh_status()
        threading.Thread(target=worker, daemon=True).start()

    def _open_zones(self, _icon=None, _item=None) -> None:
        def worker():
            if not open_admin(url=f"{DEFAULT_ADMIN_URL}#zones"):
                self._notify(
                    "Local zone editor is not ready. Check the ONEVO Connector service."
                )
            self._refresh_status()
        threading.Thread(target=worker, daemon=True).start()

    def _start_monitoring(self, _icon=None, _item=None) -> None:
        def worker():
            self.status = "Starting"
            if self.icon is not None:
                self.icon.update_menu()
            if request_resume_monitoring():
                self._notify("Starting monitoring. The dashboard will be ready shortly.")
                if wait_for_health():
                    webbrowser.open(DEFAULT_ADMIN_URL)
            else:
                self._notify("Administrator approval is required to start monitoring.")
            self._refresh_status()
        threading.Thread(target=worker, daemon=True).start()

    def _pause_monitoring(self, _icon=None, _item=None) -> None:
        """Pause through the same local API used by the connector page."""
        def worker():
            try:
                response = requests.post(
                    f"{DEFAULT_ADMIN_URL}capture/pause", timeout=10
                )
                response.raise_for_status()
                self._notify("Monitoring is stopping. Use Start monitoring when ready.")
            except requests.RequestException:
                self._notify("Could not pause monitoring. Open the local connector page for details.")
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
                    lambda _item: (
                        f"Updating to {self.latest_version}..."
                        if self.update_busy
                        else f"Update available — v{self.latest_version}"
                    ),
                    self._install_update,
                    enabled=lambda _item: not self.update_busy,
                    visible=lambda _item: self.update_available,
                ),
                pystray.MenuItem(
                    "Open Connector",
                    self._open_dashboard,
                    default=True,
                ),
                pystray.MenuItem("Edit Zones", self._open_zones),
                pystray.MenuItem(
                    "Pause monitoring",
                    self._pause_monitoring,
                    visible=lambda _item: (
                        not pause_marker_path().exists() and
                        service_status() == "running"
                    ),
                ),
                pystray.MenuItem(
                    "Start monitoring",
                    self._start_monitoring,
                    visible=lambda _item: (
                        pause_marker_path().exists()
                        or service_status() == "stopped"
                    ),
                ),
                pystray.MenuItem(
                    "Restart Connector",
                    self._restart_service,
                    visible=lambda _item: not pause_marker_path().exists(),
                ),
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
            threading.Thread(target=self._check_updates, daemon=True).start()
            threading.Thread(target=self._status_loop, daemon=True).start()
            self.icon.run()
            return 0
        finally:
            self.stop_event.set()
            self.lock.release()


def run_tray() -> int:
    return TrayApplication().run()

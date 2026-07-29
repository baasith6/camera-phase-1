"""PyInstaller entry point for the ONEVO connector.

Keep this module outside the app package so importing app.main always creates
the correct package context for its relative imports.
"""
import sys


def notify_uninstall() -> int:
    """Best-effort cloud status update before Inno Setup removes local data."""
    from app.backend_client import BackendClient
    from app.config import load_config
    from app.store import LocalStore

    cfg = load_config([])
    store = LocalStore(cfg.state_dir)
    try:
        connector_id = store.get_cred("connector_id")
        api_key = store.get_cred("api_key")
        if not connector_id or not api_key:
            return 0
        client = BackendClient(cfg.backend_url)
        client.set_credentials(connector_id, api_key)
        client.notify_uninstall()
        return 0
    except Exception:
        # Uninstall must still succeed when the shop is temporarily offline.
        return 0
    finally:
        store.close()


def dispatch(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--tray-exit" in args:
        from app.tray import request_tray_exit
        return request_tray_exit()
    if "--tray-uninstall" in args:
        from app.tray import uninstall_tray
        return uninstall_tray()
    if "--notify-uninstall" in args:
        return notify_uninstall()
    if "--open-admin" in args:
        from app.tray import open_admin
        return 0 if open_admin() else 2
    if "--start-monitoring" in args:
        from app.tray import resume_monitoring
        return 0 if resume_monitoring() else 2
    if "--tray" in args:
        from app.tray import run_tray
        return run_tray()

    from app.main import main
    return main()


if __name__ == "__main__":
    raise SystemExit(dispatch())

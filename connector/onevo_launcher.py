"""PyInstaller entry point for the ONEVO connector.

Keep this module outside the app package so importing app.main always creates
the correct package context for its relative imports.
"""
import sys


def dispatch(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--tray-exit" in args:
        from app.tray import request_tray_exit
        return request_tray_exit()
    if "--tray-uninstall" in args:
        from app.tray import uninstall_tray
        return uninstall_tray()
    if "--open-admin" in args:
        from app.tray import open_admin
        return 0 if open_admin() else 2
    if "--tray" in args:
        from app.tray import run_tray
        return run_tray()

    from app.main import main
    return main()


if __name__ == "__main__":
    raise SystemExit(dispatch())

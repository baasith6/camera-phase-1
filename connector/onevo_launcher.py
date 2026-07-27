"""PyInstaller entry point for the ONEVO connector.

Keep this module outside the app package so importing app.main always creates
the correct package context for its relative imports.
"""
from app.main import main


if __name__ == "__main__":
    raise SystemExit(main())

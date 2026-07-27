"""Allow `python -m app` and PyInstaller entry via app/__main__.py."""
from .main import main
import sys

if __name__ == "__main__":
    sys.exit(main())

"""Compatibility wrapper for legacy init_db entrypoint."""
from init_database import main


if __name__ == '__main__':
    raise SystemExit(main(['--env', 'development']))
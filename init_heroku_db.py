#!/usr/bin/env python3
"""Initialize or reset the Heroku-hosted database for Martingale."""
from init_database import main


if __name__ == '__main__':
    raise SystemExit(main(['--env', 'production']))
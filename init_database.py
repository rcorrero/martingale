#!/usr/bin/env python3
"""Reset and initialize Martingale database schemas for the current asset_id model."""
import argparse
import logging
import os
from pathlib import Path
from typing import Optional

from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from config import config as config_map
from models import db, Asset, PriceData
from asset_manager import AssetManager


LOGGER = logging.getLogger("martingale.init_database")
if not LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    LOGGER.addHandler(handler)
LOGGER.setLevel(logging.INFO)

PROJECT_ROOT = Path(__file__).resolve().parent


def build_app(env: str) -> Flask:
    """Create a lightweight Flask app configured for the requested environment."""
    config_class = config_map.get(env, config_map['default'])
    flask_app = Flask("martingale_init")
    flask_app.config.from_object(config_class)
    db.init_app(flask_app)
    return flask_app


def remove_sqlite_file(database_uri: str) -> Optional[Path]:
    """Delete the SQLite file for a clean reset when using sqlite:/// URIs."""
    if not database_uri.startswith('sqlite:///'):
        return None

    raw_path = database_uri.replace('sqlite:///', '', 1)
    db_path = (PROJECT_ROOT / raw_path).resolve() if not os.path.isabs(raw_path) else Path(raw_path)

    if db_path.exists():
        try:
            db_path.unlink()
            LOGGER.info("Deleted SQLite database at %s", db_path)
        except OSError as exc:
            LOGGER.warning("Failed to delete SQLite database %s: %s", db_path, exc)
    else:
        LOGGER.info("SQLite database %s did not exist", db_path)
    return db_path


def reset_schema(reset: bool, delete_sqlite: bool) -> None:
    """Drop all tables and optionally delete the SQLite file."""
    if not reset:
        return

    db.session.remove()
    database_uri = db.engine.url.render_as_string(hide_password=False)
    try:
        db.reflect()
        db.drop_all()
        LOGGER.info("Existing tables dropped")
    except SQLAlchemyError as exc:
        LOGGER.warning("Drop all tables raised %s; continuing", exc)
    finally:
        db.engine.dispose()
    if delete_sqlite:
        remove_sqlite_file(database_uri)


def seed_price_data(app_config) -> int:
    """Populate the PriceData table from the configured ASSETS mapping."""
    assets_config = app_config.get('ASSETS', {})
    if not assets_config:
        LOGGER.info("No ASSETS configuration found; skipping price data seeding")
        return 0

    rows = PriceData.query.count()
    if rows:
        LOGGER.info("Clearing %d existing price data rows", rows)
        PriceData.query.delete()

    created = 0
    for symbol, settings in assets_config.items():
        price_data = PriceData(
            symbol=symbol,
            current_price=settings.get('price', app_config.get('INITIAL_ASSET_PRICE', 100.0)),
            volatility=settings.get('volatility', 0.02),
            history='[]'
        )
        db.session.add(price_data)
        created += 1

    LOGGER.info("Seeded %d price data rows", created)
    return created


def seed_asset_pool(app_config) -> int:
    """Ensure there are active assets in the database matching MIN_ACTIVE_ASSETS."""
    target = app_config.get('MIN_ACTIVE_ASSETS', 16)
    active_count = Asset.query.filter_by(is_active=True).count()
    if active_count >= target:
        LOGGER.info("Asset pool already has %d active assets", active_count)
        return 0

    manager = AssetManager(app_config, price_service=None, socketio=None)
    created_assets = target - active_count
    manager.create_new_assets(count=created_assets)
    LOGGER.info("Created %d active assets", created_assets)
    return created_assets


def initialize_database(env: str, reset: bool, seed_prices: bool, seed_assets: bool, delete_sqlite: bool) -> None:
    """Perform the full initialization workflow for the selected environment."""
    flask_app = build_app(env)

    with flask_app.app_context():
        LOGGER.info("Initializing database for %s environment", env)
        reset_schema(reset=reset, delete_sqlite=delete_sqlite)

        db.create_all()
        LOGGER.info("Database tables created")

        if seed_prices:
            seed_price_data(flask_app.config)

        if seed_assets:
            seed_asset_pool(flask_app.config)

        db.session.commit()
        LOGGER.info("Database initialization complete")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset and initialize Martingale databases.")
    parser.add_argument('--env', default=os.environ.get('FLASK_ENV', 'development'), choices=config_map.keys(),
                        help='Configuration environment to use (default: %(default)s)')
    parser.add_argument('--no-reset', action='store_true', help='Skip dropping existing tables')
    parser.add_argument('--skip-price-seed', action='store_true', help='Skip reseeding price data')
    parser.add_argument('--skip-asset-seed', action='store_true', help='Skip rebuilding the active asset pool')
    parser.add_argument('--keep-sqlite-file', action='store_true',
                        help='Keep existing SQLite file instead of deleting it on reset')
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    try:
        initialize_database(
            env=args.env,
            reset=not args.no_reset,
            seed_prices=not args.skip_price_seed,
            seed_assets=not args.skip_asset_seed,
            delete_sqlite=not args.keep_sqlite_file,
        )
    except SQLAlchemyError as exc:
        LOGGER.error("Initialization failed: %s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Unexpected error during initialization: %s", exc)
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())

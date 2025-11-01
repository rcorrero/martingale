#!/usr/bin/env python3
"""Integration smoke test that starts the price service and web application together."""
import os
import subprocess
import sys
import time
from typing import List, Optional

import requests

import logging


logger = logging.getLogger("services_startup_test")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


class ManagedProcess:
    """Simple wrapper to manage subprocess lifecycle."""

    def __init__(self, name: str, args: List[str], env: Optional[dict[str, str]] = None):
        self.name = name
        self.args = args
        self.env = env
        self.process: Optional[subprocess.Popen[bytes]] = None

    def start(self) -> None:
        logger.info("Starting %s ...", self.name)
        self.process = subprocess.Popen(self.args, env=self.env)

    def terminate(self) -> None:
        if not self.process:
            return
        if self.process.poll() is not None:
            return
        logger.info("Stopping %s ...", self.name)
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("%s did not stop in time, killing", self.name)
            self.process.kill()
        finally:
            self.process = None


def wait_for_http(url: str, name: str, attempts: int = 30, delay: float = 1.0) -> bool:
    """Poll an HTTP endpoint until it responds without connection errors."""
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, timeout=2)
            if response.status_code < 500:
                logger.info("%s is reachable (attempt %d, status %d)", name, attempt, response.status_code)
                return True
            logger.warning("%s responded with status %d (attempt %d)", name, response.status_code, attempt)
        except requests.RequestException as exc:
            logger.debug("Attempt %d to reach %s failed: %s", attempt, name, exc)
        time.sleep(delay)
    logger.error("%s did not become available at %s", name, url)
    return False


def main() -> int:
    base_env = os.environ.copy()
    base_env.setdefault("FLASK_ENV", "development")
    base_env.setdefault("DATABASE_URL", "sqlite:///martingale.db")

    price_service = ManagedProcess(
        name="Price service",
        args=[sys.executable, "price_service.py"],
        env=base_env,
    )

    web_env = base_env.copy()
    web_env.setdefault("FLASK_DEBUG", "False")  # disable reloader for deterministic shutdown
    web_env.setdefault("FLASK_PORT", "5000")
    web_env.setdefault("SECRET_KEY", "dev-secret-key-for-tests")

    web_app = ManagedProcess(
        name="Web application",
        args=[sys.executable, "app.py"],
        env=web_env,
    )

    processes = [price_service, web_app]

    try:
        price_service.start()
        if not wait_for_http("http://localhost:5001/health", "Price service"):
            return 1

        web_app.start()
        if not wait_for_http("http://localhost:5000/", "Web application"):
            return 1

        # Verify that the price API is returning data (ensures real generator is active)
        prices = requests.get("http://localhost:5001/prices", timeout=3).json()
        if not prices:
            logger.error("Price service returned no price data")
            return 1
        logger.info("Price service reporting %d active assets", len(prices))

        logger.info("Both services started successfully. Sleeping briefly to observe logs...")
        time.sleep(5)
        logger.info("Smoke test complete.")
        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    finally:
        for proc in processes:
            proc.terminate()


if __name__ == "__main__":
    sys.exit(main())

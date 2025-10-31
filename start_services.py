#!/usr/bin/env python3
"""
Martingale Services Startup Script
Starts both the price service and web application.
"""
import subprocess
import time
import requests
import sys
import signal
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def start_price_service():
    """Start the price service in the background."""
    logger.info("Starting price service...")
    return subprocess.Popen([sys.executable, 'price_service.py'])

def wait_for_price_service(max_attempts=10):
    """Wait for the price service to become available."""
    for attempt in range(max_attempts):
        try:
            response = requests.get('http://localhost:5001/health', timeout=1)
            if response.status_code == 200:
                logger.info(f"✓ Price service is ready (attempt {attempt + 1})")
                return True
        except requests.exceptions.RequestException:
            pass
        logger.debug(f"Waiting for price service... (attempt {attempt + 1}/{max_attempts})")
        time.sleep(1)
    return False

def start_web_app():
    """Start the web application."""
    logger.info("Starting web application...")
    return subprocess.Popen([sys.executable, 'app.py'])

def main():
    """Main startup function."""
    price_process = None
    web_process = None
    
    try:
        # Start price service
        price_process = start_price_service()
        
        # Wait for price service to be ready
        if not wait_for_price_service():
            logger.error("❌ Price service failed to start within timeout")
            return 1
        
        # Start web application
        web_process = start_web_app()
        
        logger.info("\n🚀 Martingale Trading Platform is running!")
        logger.info("📊 Price Service: http://localhost:5001")
        logger.info("🌐 Web Application: http://localhost:5000")
        logger.info("\nPress Ctrl+C to stop all services...\n")
        
        # Wait for web process to complete or be interrupted
        web_process.wait()
        
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down services...")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return 1
    finally:
        # Clean up processes
        if web_process:
            try:
                web_process.terminate()
                web_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                web_process.kill()
        
        if price_process:
            try:
                price_process.terminate()
                price_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                price_process.kill()
        
        logger.info("✅ All services stopped")
    
    return 0

if __name__ == "__main__":
    exit(main())
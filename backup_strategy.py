"""
Database backup strategy for Heroku deployment.
This creates backups of the PostgreSQL database.
Note: This replaces the old JSON file backup system.
"""
import os
import subprocess
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def backup_database_to_heroku():
    """
    Create a backup of the Heroku Postgres database.
    This uses Heroku's built-in pg:backups feature.
    """
    try:
        # Create a backup using Heroku CLI
        # Note: This requires Heroku CLI to be installed
        result = subprocess.run([
            'heroku', 'pg:backups:capture', '--app', os.environ.get('HEROKU_APP_NAME', 'your-app-name')
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"Database backup created successfully")
            return True
        else:
            logger.error(f"Database backup failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error creating database backup: {e}")
        return False

def export_database_sql():
    """
    Export database to SQL format for manual backup.
    This is useful for local development backups.
    """
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL not found")
        return False
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"martingale_backup_{timestamp}.sql"
        
        # Use pg_dump to create SQL backup
        result = subprocess.run([
            'pg_dump', database_url, '-f', backup_file
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"SQL backup created: {backup_file}")
            return backup_file
        else:
            logger.error(f"SQL backup failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error creating SQL backup: {e}")
        return False

# Note: The old JSON file backup system has been replaced with PostgreSQL database storage.
# This file has been updated to work with the new database architecture.
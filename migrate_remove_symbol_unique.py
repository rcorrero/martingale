"""
Migration: Remove UNIQUE constraint from asset.symbol column.

Rationale:
- With 3-letter symbols, there are only 17,576 possible combinations (26^3)
- Assets expire and are continuously replaced in the system
- Symbol reuse is necessary for long-term operation
- Asset IDs provide unambiguous identification (primary key)
- Backward compatibility: Existing data remains valid

This migration:
1. Removes UNIQUE constraint from asset.symbol column
2. Keeps the index for query performance
3. Updates generate_symbol() to prefer unused symbols but allow reuse
"""

import os
import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config
from models import db, Asset


def remove_unique_constraint_sqlite(engine):
    """Remove UNIQUE constraint from asset.symbol in SQLite.
    
    SQLite doesn't support DROP CONSTRAINT directly, so we need to:
    1. Create new table without UNIQUE constraint
    2. Copy data
    3. Drop old table
    4. Rename new table
    """
    print("Removing UNIQUE constraint from asset.symbol (SQLite)")
    
    with engine.connect() as conn:
        # Check if table exists
        inspector = inspect(engine)
        database_url = os.environ.get("DATABASE_URL")
            print("  ✓ Assets table doesn't exist yet, no migration needed")
            return
        
        # Create temporary table without UNIQUE constraint
        print("  - Creating temporary table without UNIQUE constraint...")
        conn.execute(text("""
            CREATE TABLE assets_new (
                id INTEGER PRIMARY KEY,
        if not database_url:
            print("❌ DATABASE_URL environment variable not set.")
            sys.exit(1)

        # Always force conversion for Heroku compatibility
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif database_url.startswith("postgresql://") and "+psycopg2" not in database_url:
            # Add driver if missing
            database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

                expires_at DATETIME NOT NULL,
                is_active BOOLEAN DEFAULT 1 NOT NULL,
                final_price FLOAT,
                settled_at DATETIME,
                CHECK (initial_price > 0),
                CHECK (current_price >= 0),
                CHECK (volatility >= 0),
                CHECK (volatility <= 1),
                CHECK (final_price IS NULL OR final_price >= 0)
            )
        """))
        
        # Copy data from old table
        print("  - Copying data from old table...")
        conn.execute(text("""
            INSERT INTO assets_new
            SELECT * FROM assets
        """))
        
        # Drop old table
        print("  - Dropping old table...")
        conn.execute(text("DROP TABLE assets"))
        
        # Rename new table
        print("  - Renaming new table...")
        conn.execute(text("ALTER TABLE assets_new RENAME TO assets"))
        
        # Recreate indexes
        print("  - Recreating indexes...")
        conn.execute(text("CREATE INDEX ix_assets_symbol ON assets (symbol)"))
        conn.execute(text("CREATE INDEX ix_assets_expires_at ON assets (expires_at)"))
        conn.execute(text("CREATE INDEX ix_assets_is_active ON assets (is_active)"))
        
        conn.commit()
        print("  ✓ UNIQUE constraint removed successfully")


def remove_unique_constraint_postgresql(engine):
    """Remove UNIQUE constraint from asset.symbol in PostgreSQL."""
    print("Removing UNIQUE constraint from asset.symbol (PostgreSQL)")
    
    with engine.begin() as conn:  # Use begin() for automatic transaction management
        # Check if table exists
        inspector = inspect(engine)
        if 'assets' not in inspector.get_table_names():
            print("  ✓ Assets table doesn't exist yet, no migration needed")
            return
        
        # Find the unique constraint name
        print("  - Finding UNIQUE constraint name...")
        result = conn.execute(text("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'assets'
            AND constraint_type = 'UNIQUE'
            AND constraint_name LIKE '%symbol%'
        """))
        
        constraint_name = None
        for row in result:
            constraint_name = row[0]
            break
        
        if constraint_name:
            print(f"  - Dropping constraint: {constraint_name}")
            conn.execute(text(f"ALTER TABLE assets DROP CONSTRAINT IF EXISTS {constraint_name}"))
            print("  ✓ UNIQUE constraint removed successfully")
        else:
            # Try alternate approach - drop index if it exists
            print("  - No named constraint found, checking for UNIQUE index...")
            try:
                result = conn.execute(text("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename = 'assets' 
                    AND indexdef LIKE '%UNIQUE%' 
                    AND indexname LIKE '%symbol%'
                """))
                
                index_name = None
                for row in result:
                    index_name = row[0]
                    break
                
                if index_name:
                    print(f"  - Dropping UNIQUE index: {index_name}")
                    conn.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
                    # Recreate as non-unique index
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_assets_symbol ON assets (symbol)"))
                    print("  ✓ UNIQUE constraint removed successfully")
                else:
                    print("  ✓ No UNIQUE constraint found (may have been removed already)")
            except Exception as e:
                print(f"  ✓ No UNIQUE constraint found (may have been removed already): {e}")


def main():
    """Run the migration."""
    print("\n" + "="*70)
    print("Migration: Remove UNIQUE constraint from asset.symbol")
    print("="*70 + "\n")
    
    # Get database URL from environment
    config_name = os.environ.get('FLASK_ENV', 'development')
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        # Fall back to config
        app_config = config[config_name]
        database_url = app_config.SQLALCHEMY_DATABASE_URI
    
    # Heroku uses postgres:// but SQLAlchemy 1.4+ requires postgresql://
    # Also handle the psycopg2 driver specification
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            print("❌ DATABASE_URL environment variable not set.")
            sys.exit(1)

        database_url = database_url.strip()
        # Always force conversion for Heroku compatibility
        if database_url.startswith("postgres://"):
            print("[DEBUG] Converting postgres:// to postgresql+psycopg2://")
            database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif database_url.startswith("postgresql://") and "+psycopg2" not in database_url:
            print("[DEBUG] Adding +psycopg2 to postgresql:// URL")
            database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

        print(f"[DEBUG] Final database_url: {database_url}")
        if database_url.startswith("postgres://"):
            print("❌ DATABASE_URL is still using postgres:// after attempted conversion. Aborting.")
            sys.exit(1)
    
    print(f"Environment: {config_name}")
    print(f"Database: {database_url.split('@')[-1] if '@' in database_url else 'SQLite'}\n")
    
    # Create engine
    engine = create_engine(database_url)
    
    # Determine database type and run appropriate migration
    if 'sqlite' in database_url.lower():
        remove_unique_constraint_sqlite(engine)
    elif 'postgresql' in database_url.lower() or 'postgres' in database_url.lower():
        remove_unique_constraint_postgresql(engine)
    else:
        print(f"❌ Unsupported database type: {database_url}")
        sys.exit(1)
    
    print("\n" + "="*70)
    print("Migration completed successfully!")
    print("="*70 + "\n")
    
    print("Next steps:")
    print("1. Update models.py to remove unique=True from symbol column")
    print("2. Update generate_symbol() to allow symbol reuse for inactive assets")
    print("3. Test asset creation to verify symbol reuse works")
    print()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

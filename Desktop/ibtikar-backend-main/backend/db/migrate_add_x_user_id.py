#!/usr/bin/env python3
"""
Migration script to add x_user_id column to x_tokens table.
Run this once after deploying the new code.

Usage:
    python -m backend.db.migrate_add_x_user_id
"""

from sqlalchemy import text
from backend.db.session import engine, Base
from backend.core.config import settings

def migrate():
    """Add x_user_id column to x_tokens table if it doesn't exist."""
    print("🔄 Running migration: Add x_user_id to x_tokens table...")
    print(f"📊 Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")
    
    try:
        with engine.connect() as conn:
            # Check if column already exists
            if "sqlite" in settings.DATABASE_URL.lower():
                # SQLite
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM pragma_table_info('x_tokens') 
                    WHERE name='x_user_id'
                """))
                exists = result.scalar() > 0
            else:
                # PostgreSQL
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM information_schema.columns 
                    WHERE table_name='x_tokens' AND column_name='x_user_id'
                """))
                exists = result.scalar() > 0
            
            if exists:
                print("✅ Column x_user_id already exists. Migration not needed.")
                return
            
            # Add the column
            if "sqlite" in settings.DATABASE_URL.lower():
                # SQLite
                conn.execute(text("ALTER TABLE x_tokens ADD COLUMN x_user_id VARCHAR(255)"))
                print("✅ Added x_user_id column to x_tokens table (SQLite)")
            else:
                # PostgreSQL
                conn.execute(text("ALTER TABLE x_tokens ADD COLUMN x_user_id VARCHAR(255)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_x_tokens_x_user_id ON x_tokens(x_user_id)"))
                print("✅ Added x_user_id column and index to x_tokens table (PostgreSQL)")
            
            conn.commit()
            print("✅ Migration completed successfully!")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise

if __name__ == "__main__":
    migrate()


#!/usr/bin/env python3
"""
Migration script to add cached user profile columns to x_tokens table.
Run this once after deploying the new code.

Usage:
    python -m backend.db.migrate_add_cached_user_profile
"""

from sqlalchemy import text
from backend.db.session import engine
from backend.core.config import settings

def migrate():
    """Add cached user profile columns to x_tokens table if they don't exist."""
    print("🔄 Running migration: Add cached user profile columns to x_tokens table...")
    print(f"📊 Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")
    
    columns_to_add = [
        ("cached_name", "VARCHAR(255)"),
        ("cached_username", "VARCHAR(255)"),
        ("cached_profile_image_url", "TEXT"),
    ]
    
    try:
        with engine.begin() as conn:
            for column_name, column_type in columns_to_add:
                # Check if column already exists
                if "sqlite" in settings.DATABASE_URL.lower():
                    # SQLite
                    result = conn.execute(text(f"""
                        SELECT COUNT(*) FROM pragma_table_info('x_tokens') 
                        WHERE name='{column_name}'
                    """))
                    exists = result.scalar() > 0
                else:
                    # PostgreSQL
                    result = conn.execute(text(f"""
                        SELECT COUNT(*) FROM information_schema.columns 
                        WHERE table_name='x_tokens' AND column_name='{column_name}'
                    """))
                    exists = result.scalar() > 0
                
                if exists:
                    print(f"✅ Column {column_name} already exists. Skipping.")
                else:
                    # Add the column
                    if "sqlite" in settings.DATABASE_URL.lower():
                        # SQLite
                        conn.execute(text(f"ALTER TABLE x_tokens ADD COLUMN {column_name} {column_type}"))
                        print(f"✅ Added {column_name} column to x_tokens table (SQLite)")
                    else:
                        # PostgreSQL
                        conn.execute(text(f"ALTER TABLE x_tokens ADD COLUMN {column_name} {column_type}"))
                        print(f"✅ Added {column_name} column to x_tokens table (PostgreSQL)")
            
            print("✅ Migration completed successfully!")
            return {"success": True, "added": True}
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    migrate()


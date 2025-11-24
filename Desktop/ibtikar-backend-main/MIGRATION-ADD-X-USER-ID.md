# Migration: Add x_user_id to x_tokens table

This migration adds a cached Twitter user ID field to avoid rate limits.

## What this fixes

- **Problem**: Every API call to `/v1/analysis/preview` calls `get_me()` which hits Twitter's rate limit
- **Solution**: Cache the Twitter user ID in the database and reuse it

## You DO have a database! 

Your backend uses:
- **SQLite** locally (file: `ngodb.sqlite3`)
- **PostgreSQL** on Render.com (via `DATABASE_URL` environment variable)

## Easy Migration (Choose One Method)

### Method 1: Run Python Script (Easiest!)

After Render redeploys, run this in your Render shell or locally:

```bash
# From the backend directory
python -m backend.db.migrate_add_x_user_id
```

Or if you're in the project root:
```bash
cd Desktop/ibtikar-backend-main
export PYTHONPATH=.
python -m backend.db.migrate_add_x_user_id
```

### Method 2: Run SQL Directly (If you have database access)

**For Render.com PostgreSQL:**
1. Go to your Render dashboard
2. Find your PostgreSQL database
3. Click "Connect" or "Shell"
4. Run:
```sql
ALTER TABLE x_tokens ADD COLUMN x_user_id VARCHAR(255) NULL;
CREATE INDEX IF NOT EXISTS ix_x_tokens_x_user_id ON x_tokens(x_user_id);
```

**For Local SQLite:**
```bash
sqlite3 ngodb.sqlite3
```
Then:
```sql
ALTER TABLE x_tokens ADD COLUMN x_user_id VARCHAR(255);
```

### Method 3: Let it auto-migrate (Simplest!)

The code will work even without the column - it will just call `get_me()` once and cache it. But to avoid the first rate limit, run the migration.

## What happens

1. **After OAuth**: The Twitter user ID is fetched once and cached
2. **On subsequent requests**: Uses cached ID instead of calling `get_me()` API
3. **Result**: No more rate limit issues from `get_me()` calls!

## Testing

After migration:
1. Re-link your Twitter account (OAuth) - this will cache your Twitter user ID
2. Test `/v1/analysis/preview` - should work without rate limits!


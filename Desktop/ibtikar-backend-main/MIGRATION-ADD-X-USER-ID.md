# Migration: Add x_user_id to x_tokens table

This migration adds a cached Twitter user ID field to avoid rate limits.

## What this fixes

- **Problem**: Every API call to `/v1/analysis/preview` calls `get_me()` which hits Twitter's rate limit
- **Solution**: Cache the Twitter user ID in the database and reuse it

## Database Migration

Run this SQL on your database:

```sql
ALTER TABLE x_tokens ADD COLUMN x_user_id VARCHAR(255) NULL;
CREATE INDEX IF NOT EXISTS ix_x_tokens_x_user_id ON x_tokens(x_user_id);
```

## What happens

1. **After OAuth**: The Twitter user ID is fetched once and cached
2. **On subsequent requests**: Uses cached ID instead of calling `get_me()` API
3. **Result**: No more rate limit issues from `get_me()` calls!

## Testing

After migration:
1. Re-link your Twitter account (OAuth) - this will cache your Twitter user ID
2. Test `/v1/analysis/preview` - should work without rate limits!


# backend/clients/x_api.py
from typing import Dict, Any
import httpx
from sqlalchemy.orm import Session

from backend.db.models import XToken
from backend.core.crypto import dec, enc
from backend.core.config import settings

API = "https://api.twitter.com/2"

# ----------------------- token helpers -----------------------

def _get_token_pair(user_id: int, db: Session) -> tuple[str, str | None, XToken]:
    row: XToken | None = db.query(XToken).filter(XToken.user_id == user_id).first()
    if not row:
        # Check if user exists at all
        from backend.db.models import User
        user_exists = db.query(User).filter(User.id == user_id).first()
        if not user_exists:
            raise RuntimeError(f"No user found for user_id={user_id}. Please complete OAuth flow first.")
        raise RuntimeError(f"No token for user_id={user_id}. Token row not found in database. Please re-link your account via /v1/oauth/x/start?user_id={user_id}")
    
    try:
        access = dec(row.access_token)
    except Exception as e:
        raise RuntimeError(f"Failed to decrypt access token for user_id={user_id}: {e}. The token may have been encrypted with a different FERNET_KEY. Please re-link your account.")
    
    try:
        refresh = dec(row.refresh_token) if row.refresh_token else None
    except Exception as e:
        print(f"⚠️ Failed to decrypt refresh token for user_id={user_id}: {e}. Using access token only.")
        refresh = None
    
    return access, refresh, row

def _client(bearer: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=API,
        headers={"Authorization": f"Bearer {bearer}"},
        timeout=20.0,
    )

async def _refresh_access_token(refresh_token: str) -> dict:
    """
    OAuth2 PKCE refresh: needs client_id, not client_secret.
    """
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.X_CLIENT_ID,
    }
    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.post(
            "https://api.twitter.com/2/oauth2/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        return r.json()

def _store_tokens(row: XToken, token_json: dict, db: Session) -> str:
    new_access = token_json.get("access_token")
    new_refresh = token_json.get("refresh_token")  # may be absent depending on X
    if new_access:
        row.access_token = enc(new_access)
    if new_refresh:
        row.refresh_token = enc(new_refresh)
    row.scope = token_json.get("scope", row.scope)
    row.token_type = token_json.get("token_type", row.token_type)
    row.expires_in = token_json.get("expires_in", row.expires_in)
    db.commit()
    return new_access or dec(row.access_token)

# ----------------------- X API wrappers -----------------------

async def get_me(user_id: int, db: Session) -> Dict[str, Any]:
    """
    Calls /users/me, auto-refreshes on 401 once, then retries.
    Returns dict with rate_limited key if 429.
    """
    access, refresh, row = _get_token_pair(user_id, db)

    async def _call(bearer: str):
        async with _client(bearer) as c:
            return await c.get("/users/me", params={"user.fields": "name,username,profile_image_url"})

    r = await _call(access)
    if r.status_code == 401 and refresh:
        tj = await _refresh_access_token(refresh)
        access = _store_tokens(row, tj, db)
        r = await _call(access)
    
    # Handle rate limiting
    if r.status_code == 429:
        reset = r.headers.get("x-rate-limit-reset")
        limit = r.headers.get("x-rate-limit-limit", "unknown")
        remaining = r.headers.get("x-rate-limit-remaining", "0")
        return {
            "rate_limited": True,
            "resource": "users/me",
            "reset": reset,
            "limit": limit,
            "remaining": remaining,
        }

    r.raise_for_status()
    return r.json()

async def get_my_recent_tweets(user_id: int, db: Session, max_results: int = 20) -> Dict[str, Any]:
    # Check if we have cached Twitter user ID to avoid rate limit
    from backend.db.models import XToken
    token_row = db.query(XToken).filter(XToken.user_id == user_id).first()
    
    # Check if column exists (for graceful migration)
    has_x_user_id = False
    cached_uid = None
    if token_row:
        try:
            cached_uid = getattr(token_row, 'x_user_id', None)
            has_x_user_id = True
        except AttributeError:
            # Column doesn't exist yet - migration not run
            has_x_user_id = False
    
    if token_row and cached_uid:
        # Use cached Twitter user ID - no need to call get_me
        uid = cached_uid
        print(f"✅ Using cached Twitter user ID: {uid} (avoiding get_me API call)")
    else:
        # No cached ID - need to call get_me (but only once)
        print(f"⚠️ No cached Twitter user ID, calling get_me (this may hit rate limit)")
        me = await get_me(user_id, db)
        if isinstance(me, dict) and me.get("rate_limited"):
            return me  # Return rate limit info
        uid = me["data"]["id"]
        
        # Cache it for next time (if column exists)
        if token_row and has_x_user_id:
            try:
                token_row.x_user_id = uid
                db.commit()
                print(f"✅ Cached Twitter user ID: {uid}")
            except Exception as e:
                print(f"⚠️ Could not cache Twitter user ID (column may not exist): {e}")
    
    access, _, _ = _get_token_pair(user_id, db)
    async with _client(access) as c:
        r = await c.get(
            f"/users/{uid}/tweets",
            params={
                "max_results": min(max_results, 100),
                "tweet.fields": "created_at,author_id,lang,public_metrics",
                "exclude": "retweets,replies",
            },
        )
        r.raise_for_status()
        return r.json()

async def get_following_feed(user_id: int, db: Session, authors_limit: int = 25, per_batch: int = 20) -> Dict[str, Any]:
    """
    Free-tier friendly fallback: own tweets + mentions.
    Returns {"data": [...]} or {"rate_limited": True, ...} when 429.
    Uses cached Twitter user ID to avoid calling get_me every time.
    """
    # Check if we have cached Twitter user ID to avoid rate limit
    from backend.db.models import XToken
    token_row = db.query(XToken).filter(XToken.user_id == user_id).first()
    
    # Check if column exists (for graceful migration)
    has_x_user_id = False
    cached_uid = None
    if token_row:
        try:
            cached_uid = getattr(token_row, 'x_user_id', None)
            has_x_user_id = True
        except AttributeError:
            # Column doesn't exist yet - migration not run
            has_x_user_id = False
    
    if token_row and cached_uid:
        # Use cached Twitter user ID - no need to call get_me
        uid = cached_uid
        print(f"✅ Using cached Twitter user ID: {uid} (avoiding get_me API call)")
    else:
        # No cached ID - need to call get_me (but only once)
        print(f"⚠️ No cached Twitter user ID, calling get_me (this may hit rate limit)")
        me = await get_me(user_id, db)
        if isinstance(me, dict) and me.get("rate_limited"):
            return me  # Return rate limit info from get_me
        uid = me["data"]["id"]
        
        # Cache it for next time (if column exists)
        if token_row and has_x_user_id:
            try:
                token_row.x_user_id = uid
                db.commit()
                print(f"✅ Cached Twitter user ID: {uid}")
            except Exception as e:
                print(f"⚠️ Could not cache Twitter user ID (column may not exist): {e}")
    
    access, _, _ = _get_token_pair(user_id, db)

    async with _client(access) as c:
        # 1) own tweets
        r1 = await c.get(
            f"/users/{uid}/tweets",
            params={
                "max_results": min(per_batch, 50),
                "tweet.fields": "created_at,author_id,lang,public_metrics",
                "exclude": "retweets,replies",
            },
        )
        if r1.status_code == 429:
            return {
                "rate_limited": True,
                "resource": "user_tweets",
                "reset": r1.headers.get("x-rate-limit-reset"),
                "limit": r1.headers.get("x-rate-limit-limit"),
                "remaining": r1.headers.get("x-rate-limit-remaining"),
            }
        r1.raise_for_status()
        data = r1.json().get("data", []) or []

        # 2) mentions
        r2 = await c.get(
            f"/users/{uid}/mentions",
            params={
                "max_results": min(per_batch, 50),
                "tweet.fields": "created_at,author_id,lang,public_metrics",
            },
        )
        if r2.status_code == 429:
            return {
                "rate_limited": True,
                "resource": "mentions",
                "reset": r2.headers.get("x-rate-limit-reset"),
                "limit": r2.headers.get("x-rate-limit-limit"),
                "remaining": r2.headers.get("x-rate-limit-remaining"),
            }
        r2.raise_for_status()
        mentions = r2.json().get("data", []) or []

    return {"data": data + mentions}

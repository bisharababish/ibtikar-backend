from datetime import datetime
import time

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from ..core.config import settings
from ..db.init_db import init_db
from ..db.session import get_db
from ..db import models
from ..core.crypto import enc
from ..core.memory import new_state, put_state, pop_state, cleanup_expired_states
from ..clients.x_client import generate_pkce, build_auth_url, exchange_code_for_token
from ..core.schemas import AnalysisResponse, AnalysisItem
from ..core.normalize import x_tweets_to_posts
from ..clients.ibtikar_client import analyze_texts
from backend.db.models import Prediction  # keep as-is since it already works
from ..clients.x_api import get_me, get_my_recent_tweets, get_following_feed

from typing import List, Optional
from pydantic import BaseModel

# ---------- Analysis schemas ----------

class AnalysisPostItem(BaseModel):
    id: int
    user_id: int
    source: str
    post_id: str
    author_id: str
    lang: Optional[str] = None
    text: str
    label: str
    score: float
    post_created_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True  # Pydantic V2: renamed from orm_mode


class AnalysisPostsResponse(BaseModel):
    total: int
    items: List[AnalysisPostItem]


class AuthorSummaryItem(BaseModel):
    author_id: str
    post_count: int
    harmful_count: int
    safe_count: int
    unknown_count: int
    harmful_ratio: float


class AuthorSummaryResponse(BaseModel):
    total: int
    items: List[AuthorSummaryItem]

# ---------- FastAPI app and endpoints ----------

app = FastAPI(title="IbtikarAI Backend", version="0.2.0")
init_db()  # create tables on startup (local dev)

# ---------- Analysis read endpoints ----------

@app.get("/v1/analysis/posts", response_model=AnalysisPostsResponse)
def list_analysis_posts(
    user_id: int,
    label: Optional[str] = None,
    author_id: Optional[str] = None,
    lang: Optional[str] = None,
    from_created_at: Optional[datetime] = None,
    to_created_at: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    List analyzed posts for a given user, with optional filters.
    Results are ordered by predictions.created_at DESC.
    """
    # basic safety on limit
    if limit > 200:
        limit = 200
    if limit < 1:
        limit = 1
    if offset < 0:
        offset = 0

    query = db.query(models.Prediction).filter(models.Prediction.user_id == user_id)

    if label:
        query = query.filter(models.Prediction.label == label)
    if author_id:
        query = query.filter(models.Prediction.author_id == author_id)
    if lang:
        query = query.filter(models.Prediction.lang == lang)
    if from_created_at:
        query = query.filter(models.Prediction.created_at >= from_created_at)
    if to_created_at:
        query = query.filter(models.Prediction.created_at <= to_created_at)

    total = query.count()

    predictions = (
        query.order_by(models.Prediction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        AnalysisPostItem(
            id=p.id,
            user_id=p.user_id,
            source=p.source,
            post_id=p.post_id,
            author_id=p.author_id,
            lang=p.lang,
            text=p.text,
            label=p.label,
            score=float(p.score),
            post_created_at=p.post_created_at,
            created_at=p.created_at,
        )
        for p in predictions
    ]

    return AnalysisPostsResponse(total=total, items=items)


@app.get("/v1/analysis/authors", response_model=AuthorSummaryResponse)
def list_author_summaries(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    Aggregate stats per author for a given user.
    Counts how many harmful/safe/unknown tweets each author has.
    """
    if limit > 200:
        limit = 200
    if limit < 1:
        limit = 1
    if offset < 0:
        offset = 0

    # Build aggregation query
    q = (
        db.query(
            models.Prediction.author_id.label("author_id"),
            func.count(models.Prediction.id).label("post_count"),
            func.sum(
                case((models.Prediction.label == "harmful", 1), else_=0)
            ).label("harmful_count"),
            func.sum(
                case((models.Prediction.label == "safe", 1), else_=0)
            ).label("safe_count"),
            func.sum(
                case(
                    (
                        models.Prediction.label.notin_(["harmful", "safe"]),
                        1,
                    ),
                    else_=0,
                )
            ).label("unknown_count"),
        )
        .filter(models.Prediction.user_id == user_id)
        .group_by(models.Prediction.author_id)
    )

    total = q.count()

    rows = (
        q.order_by(func.sum(case((models.Prediction.label == "harmful", 1), else_=0)).desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items: List[AuthorSummaryItem] = []
    for row in rows:
        post_count = int(row.post_count or 0)
        harmful_count = int(row.harmful_count or 0)
        safe_count = int(row.safe_count or 0)
        unknown_count = int(row.unknown_count or 0)

        harmful_ratio = float(harmful_count / post_count) if post_count > 0 else 0.0

        items.append(
            AuthorSummaryItem(
                author_id=str(row.author_id),
                post_count=post_count,
                harmful_count=harmful_count,
                safe_count=safe_count,
                unknown_count=unknown_count,
                harmful_ratio=harmful_ratio,
            )
        )

    return AuthorSummaryResponse(total=total, items=items)

@app.get("/health")
def health():
    """Health check endpoint - should not require database or external services"""
    try:
        return {
            "status": "ok",
            "service": "ibtikar-backend",
            "env": settings.ENV,
            "version": "0.2.0",
        }
    except Exception as e:
        # Even if settings fail, return basic health
        return {
            "status": "degraded",
            "service": "ibtikar-backend",
            "error": str(e),
        }


def ensure_local_user(db: Session) -> int:
    u = db.query(models.User).filter(models.User.id == 1).first()
    if not u:
        u = models.User(id=1)
        db.add(u)
        db.commit()
    return 1


@app.get("/v1/oauth/x/start")
async def x_oauth_start(user_id: int = 1, db: Session = Depends(get_db)):
    # ensure user exists
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        db.add(models.User(id=user_id))
        db.commit()

    # Ensure OAuthState table exists (create if it doesn't)
    try:
        from backend.db.models import OAuthState
        from backend.db.session import Base, engine
        Base.metadata.create_all(bind=engine, tables=[OAuthState.__table__], checkfirst=True)
    except Exception as e:
        print(f"⚠️ Could not ensure OAuthState table exists: {e}")

    verifier, challenge = generate_pkce()
    state = new_state()
    # store BOTH verifier and user_id in database (not memory)
    # Increased TTL to 30 minutes to allow more time for user authorization
    print(f"🔐 Creating OAuth state: {state[:10]}... for user_id={user_id}")
    put_state(state, verifier, user_id, ttl_seconds=1800, db=db)
    # ALWAYS force login - this ensures user can switch accounts every time
    twitter_auth_url = build_auth_url(state, challenge, force_login=True)
    
    # Direct redirect to Twitter - this should work better than HTML page
    # force_login=true will force Twitter to show login screen every time
    return RedirectResponse(url=twitter_auth_url)


@app.get("/v1/oauth/x/callback")
async def x_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
):
    # Handle OAuth errors from Twitter
    if error:
        error_msg = f"OAuth error: {error}"
        if error_description:
            error_msg += f" - {error_description}"
        print(f"❌ OAuth callback error: {error_msg}")
        # Redirect to app with error
        app_redirect_url = f"ibtikar://oauth/callback?success=false&error={error}"
        return RedirectResponse(url=app_redirect_url)
    
    if not code or not state:
        print(f"❌ OAuth callback missing parameters: code={code is not None}, state={state is not None}")
        raise HTTPException(status_code=400, detail="Missing code/state")

    state_data = pop_state(state, db=db)
    if not state_data:
        print(f"❌ OAuth callback invalid/expired state: {state}")
        # Clean up expired states
        cleanup_expired_states(db)
        raise HTTPException(status_code=400, detail="State expired/invalid. Please try the OAuth flow again.")

    code_verifier = state_data["verifier"]
    user_id = int(state_data["user_id"])

    # Log callback details for debugging
    print(f"📥 OAuth callback received:")
    print(f"   Code: {code[:20] if code else None}...")
    print(f"   State: {state}")
    print(f"   User ID: {user_id}")
    print(f"   Expected redirect URI: {settings.X_REDIRECT_URI}")

    try:
        print(f"🔄 Exchanging OAuth code for token...")
        token = await exchange_code_for_token(code, code_verifier)
        print(f"✅ Token exchange successful for user {user_id}")
    except Exception as e:
        print(f"❌ Token exchange failed: {str(e)}")
        # Redirect to app with error
        app_redirect_url = f"ibtikar://oauth/callback?success=false&error=token_exchange_failed"
        return RedirectResponse(url=app_redirect_url)

    # ensure this user exists
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        db.add(models.User(id=user_id))
        db.commit()

    existing = db.query(models.XToken).filter(models.XToken.user_id == user_id).first()
    if not existing:
        db.add(
            models.XToken(
                user_id=user_id,
                access_token=enc(token.get("access_token", "")),
                refresh_token=enc(token.get("refresh_token", ""))
                if token.get("refresh_token")
                else None,
                scope=token.get("scope"),
                token_type=token.get("token_type"),
                expires_in=token.get("expires_in"),
            )
        )
        db.commit()  # Commit to get the ID
        existing = db.query(models.XToken).filter(models.XToken.user_id == user_id).first()
    else:
        existing.access_token = enc(token.get("access_token", ""))
        existing.refresh_token = (
            enc(token.get("refresh_token", ""))
            if token.get("refresh_token")
            else None
        )
        existing.scope = token.get("scope")
        existing.token_type = token.get("token_type")
        existing.expires_in = token.get("expires_in")

    # Fetch and cache Twitter user ID to avoid rate limits
    if not existing.x_user_id:
        try:
            print(f"📥 Fetching Twitter user ID to cache...")
            me = await get_me(user_id, db)
            if isinstance(me, dict) and not me.get("rate_limited") and me.get("data"):
                existing.x_user_id = me["data"]["id"]
                print(f"✅ Cached Twitter user ID: {existing.x_user_id}")
            else:
                print(f"⚠️ Could not fetch Twitter user ID (rate limited or error)")
        except Exception as e:
            print(f"⚠️ Error fetching Twitter user ID: {e} (will fetch on first use)")

    db.commit()
    
    # Redirect back to the Expo app using deep linking
    # The app scheme is "ibtikar" as defined in app.json
    app_redirect_url = f"ibtikar://oauth/callback?success=true&user_id={user_id}"
    return RedirectResponse(url=app_redirect_url)


@app.get("/v1/oauth/debug")
def oauth_debug():
    """Debug endpoint to check OAuth configuration."""
    return {
        "client_id": settings.X_CLIENT_ID[:10] + "..." if settings.X_CLIENT_ID else "NOT SET",
        "redirect_uri": str(settings.X_REDIRECT_URI),
        "scopes": settings.X_SCOPES,
        "env": settings.ENV,
    }

@app.post("/v1/migrate/add-x-user-id")
async def migrate_add_x_user_id():
    """
    One-time migration endpoint to add x_user_id column.
    Call this once after deploying the new code.
    Safe to call multiple times - won't duplicate the column.
    """
    from backend.db.migrate_add_x_user_id import migrate
    try:
        result = migrate()
        if result and result.get("already_exists"):
            return {
                "success": True,
                "message": "Column x_user_id already exists. Migration not needed.",
                "already_exists": True
            }
        return {
            "success": True,
            "message": "Migration completed successfully! x_user_id column added to x_tokens table.",
            "added": True
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Migration endpoint error: {error_details}")
        return {
            "success": False,
            "error": str(e),
            "message": "Migration failed. Check server logs for details."
        }

@app.get("/v1/me/link-status")
def link_status(user_id: int = 1, db: Session = Depends(get_db)):
    xt = db.query(models.XToken).filter(models.XToken.user_id == user_id).first()
    return {
        "user_id": user_id,
        "linked": bool(xt),
        "scopes": xt.scope if xt else None,
    }


@app.get("/v1/x/me")
async def x_me(user_id: int = Query(1), db: Session = Depends(get_db)):
    return await get_me(user_id, db)

@app.get("/v1/oauth/x/clear")
@app.delete("/v1/oauth/x/clear")
async def clear_oauth_tokens(user_id: int = Query(1), db: Session = Depends(get_db)):
    """
    Clear OAuth tokens for a user. Use this to switch Twitter accounts.
    After clearing, you'll need to OAuth again with the new account.
    """
    token = db.query(models.XToken).filter(models.XToken.user_id == user_id).first()
    if token:
        db.delete(token)
        db.commit()
        return {
            "success": True,
            "message": f"OAuth tokens cleared for user_id={user_id}. You can now OAuth with a different account."
        }
    return {
        "success": True,
        "message": f"No tokens found for user_id={user_id}. You can OAuth with any account."
    }


@app.get("/v1/x/my-posts")
async def x_my_posts(
    user_id: int = Query(1),
    limit: int = Query(20),
    db: Session = Depends(get_db),
):
    return await get_my_recent_tweets(user_id, db, max_results=limit)


@app.get("/v1/x/feed")
async def x_feed(
    user_id: int = Query(1),
    authors_limit: int = Query(25),
    per_batch: int = Query(20),
    db: Session = Depends(get_db),
):
    """
    “Timeline-lite”: pulls recent posts from accounts the user follows.
    Good enough for Free/Basic tiers. For stricter limits, reduce authors_limit/per_batch.
    """
    return await get_following_feed(
        user_id, db, authors_limit=authors_limit, per_batch=per_batch
    )


@app.get("/v1/x/feed/normalized")
async def x_feed_normalized(
    user_id: int = Query(1),
    authors_limit: int = Query(15),
    per_batch: int = Query(15),
    db: Session = Depends(get_db),
):
    raw = await get_following_feed(
        user_id, db, authors_limit=authors_limit, per_batch=per_batch
    )
    if isinstance(raw, dict) and raw.get("rate_limited"):
        reset = raw.get("reset")
        try:
            reset_human = (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(reset)))
                if reset
                else None
            )
        except Exception:
            reset_human = None
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "resource": raw.get("resource"),
                "reset_epoch": reset,
                "reset_time": reset_human,
                "limit": raw.get("limit"),
                "remaining": raw.get("remaining"),
            },
        )

    return {"items": [p.dict() for p in x_tweets_to_posts(raw)]}


@app.post("/v1/analysis/preview", response_model=AnalysisResponse)
async def analysis_preview(
    user_id: int = Query(1),
    authors_limit: int = Query(15),
    per_batch: int = Query(15),
    db: Session = Depends(get_db),
):
    try:
        raw = await get_following_feed(
            user_id, db, authors_limit=authors_limit, per_batch=per_batch
        )
        if isinstance(raw, dict) and raw.get("rate_limited"):
            reset = raw.get("reset")
            try:
                reset_human = (
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(reset)))
                    if reset
                    else None
                )
            except Exception:
                reset_human = None
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limited",
                    "resource": raw.get("resource"),
                    "reset_epoch": reset,
                    "reset_time": reset_human,
                    "limit": raw.get("limit"),
                    "remaining": raw.get("remaining"),
                },
            )

        posts = x_tweets_to_posts(raw)
        if not posts:
            return AnalysisResponse(
                items=[], harmful_count=0, safe_count=0, unknown_count=0
            )

        try:
            print(f"📝 Calling analyze_texts with {len(posts)} posts")
            print(f"📝 First post text sample: {posts[0].text[:50] if posts else 'N/A'}...")
            preds = await analyze_texts([p.text for p in posts])
            print(f"✅ Received {len(preds)} predictions from analyze_texts")
            print(f"📊 First prediction: {preds[0] if preds else 'N/A'}")
            print(f"📊 All predictions: {preds}")
        except Exception as e:
            # Handle rate limit errors from model API
            if "rate limit" in str(e).lower() or "429" in str(e) or "Rate limited" in str(e):
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limited",
                        "resource": "model_api",
                        "message": str(e),
                    }
                )
            # Re-raise other errors
            raise

        items: list[AnalysisItem] = []
        hc = sc = uc = 0

        for p, pr in zip(posts, preds):
            label = pr.get("label", "unknown")
            score = float(pr.get("score", 0.0))

            items.append(AnalysisItem(post=p, label=label, score=score))
            if label == "harmful":
                hc += 1
            elif label == "safe":
                sc += 1
            else:
                uc += 1

            # Key we use to avoid duplicates
            post_id_str = str(p.post_id) if getattr(p, "post_id", None) is not None else None

            # Check if a prediction for this (user, source, post_id) already exists
            existing_pred = (
                db.query(Prediction)
                .filter(
                    Prediction.user_id == user_id,
                    Prediction.source == "x",
                    Prediction.post_id == post_id_str,
                )
                .first()
            )

            if existing_pred:
                # Update existing prediction instead of inserting a duplicate
                existing_pred.author_id = (
                    str(p.author_id) if getattr(p, "author_id", None) else None
                )
                existing_pred.lang = getattr(p, "lang", None)
                existing_pred.text = p.text
                existing_pred.label = label
                existing_pred.score = score
                existing_pred.post_created_at = (
                    p.created_at if isinstance(p.created_at, datetime) else None
                )
                existing_pred.created_at = datetime.utcnow()
            else:
                # Create a new prediction
                db_obj = Prediction(
                    user_id=user_id,
                    source="x",
                    post_id=post_id_str,
                    author_id=(
                        str(p.author_id) if getattr(p, "author_id", None) else None
                    ),
                    lang=getattr(p, "lang", None),
                    text=p.text,
                    label=label,
                    score=score,
                    post_created_at=(
                        p.created_at if isinstance(p.created_at, datetime) else None
                    ),
                )
                db.add(db_obj)

        # Save all changes (new + updated) at once
        db.commit()
        print(f"💾 Saved {len(items)} predictions to database (harmful: {hc}, safe: {sc}, unknown: {uc})")

        return AnalysisResponse(
            items=items,
            harmful_count=hc,
            safe_count=sc,
            unknown_count=uc,
        )
    except HTTPException:
        # Re-raise HTTP exceptions (like 429 rate limit)
        raise
    except Exception as e:
        # Log the error for debugging
        import traceback
        print(f"❌ Error in analysis_preview: {e}")
        print(traceback.format_exc())
        # Return a user-friendly error
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_server_error",
                "message": str(e),
                "hint": "This might be due to Twitter API issues, database connection, or model API problems. Please try again later."
            }
        )

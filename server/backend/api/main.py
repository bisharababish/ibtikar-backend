from datetime import datetime
import time

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from ..core.config import settings
from ..db.init_db import init_db
from ..db.session import get_db
from ..db import models
from ..core.crypto import enc
from ..core.memory import new_state, put_state, pop_state
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
        orm_mode = True


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

# ---------- Static files for Play Console documentation ----------
# Get the path to the static directory (server/static)
# Try multiple possible paths to handle different deployment scenarios
import os
import logging

logger = logging.getLogger(__name__)

# Try multiple paths in order of likelihood
possible_paths = [
    # Path relative to this file (most common)
    Path(__file__).parent.parent.parent / "static",  # server/backend/api -> server/static
    # Paths relative to current working directory
    Path(os.getcwd()) / "server" / "static",
    Path(os.getcwd()) / "static",
    # Absolute paths from common Render structures
    Path("/opt/render/project/src/server/static"),
    Path("/app/server/static"),
    # Relative paths as last resort
    Path("server/static"),
    Path("static"),
]

static_dir = None
for path in possible_paths:
    if path.exists() and (path / "privacy-policy.html").exists():
        static_dir = path
        logger.info(f"Found static directory at: {static_dir.absolute()}")
        break

if static_dir and static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info(f"Mounted static files from: {static_dir.absolute()}")
else:
    logger.warning(f"Static directory not found! Tried paths: {[str(p) for p in possible_paths]}")
    logger.warning(f"Current working directory: {os.getcwd()}")
    logger.warning(f"__file__ location: {__file__}")
    # Create a dummy static_dir to prevent errors
    static_dir = Path(__file__).parent.parent.parent / "static"

# Direct routes for easy access (for Play Console)
@app.get("/privacy-policy.html")
async def privacy_policy():
    """Privacy Policy page for Google Play Console"""
    # Try multiple possible locations
    possible_files = [
        static_dir / "privacy-policy.html",
        Path(os.getcwd()) / "server" / "static" / "privacy-policy.html",
        Path(os.getcwd()) / "static" / "privacy-policy.html",
        Path(__file__).parent.parent.parent / "static" / "privacy-policy.html",
    ]
    
    for file_path in possible_files:
        if file_path.exists():
            logger.info(f"Serving privacy-policy.html from: {file_path.absolute()}")
            return FileResponse(file_path, media_type="text/html")
    
    logger.error(f"Privacy policy not found! Tried: {[str(p) for p in possible_files]}")
    logger.error(f"CWD: {os.getcwd()}, __file__: {__file__}")
    raise HTTPException(status_code=404, detail=f"Privacy policy not found. CWD: {os.getcwd()}")

@app.get("/delete-account.html")
async def delete_account():
    """Delete Account page for Google Play Console"""
    # Try multiple possible locations
    possible_files = [
        static_dir / "delete-account.html",
        Path(os.getcwd()) / "server" / "static" / "delete-account.html",
        Path(os.getcwd()) / "static" / "delete-account.html",
        Path(__file__).parent.parent.parent / "static" / "delete-account.html",
    ]
    
    for file_path in possible_files:
        if file_path.exists():
            logger.info(f"Serving delete-account.html from: {file_path.absolute()}")
            return FileResponse(file_path, media_type="text/html")
    
    logger.error(f"Delete account page not found! Tried: {[str(p) for p in possible_files]}")
    logger.error(f"CWD: {os.getcwd()}, __file__: {__file__}")
    raise HTTPException(status_code=404, detail=f"Delete account page not found. CWD: {os.getcwd()}")

@app.get("/debug/static-paths")
async def debug_static_paths():
    """Debug endpoint to check static file paths (remove in production)"""
    import os
    from pathlib import Path
    
    info = {
        "cwd": os.getcwd(),
        "__file__": __file__,
        "static_dir": str(static_dir) if static_dir else None,
        "static_dir_exists": static_dir.exists() if static_dir else False,
        "possible_paths": []
    }
    
    possible_paths = [
        Path(__file__).parent.parent.parent / "static",
        Path(os.getcwd()) / "server" / "static",
        Path(os.getcwd()) / "static",
        Path("server/static"),
        Path("static"),
    ]
    
    for path in possible_paths:
        info["possible_paths"].append({
            "path": str(path),
            "absolute": str(path.absolute()),
            "exists": path.exists(),
            "has_privacy": (path / "privacy-policy.html").exists() if path.exists() else False,
            "has_delete": (path / "delete-account.html").exists() if path.exists() else False,
        })
    
    return info

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
    return {
        "status": "ok",
        "service": "ibtikar-backend",
        "env": settings.ENV,
        "version": "0.2.0",
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
    print("=" * 80)
    print("≡اأ OAuth Start Request")
    print(f"   User ID: {user_id}")
    print("=" * 80)
    
    # ensure user exists
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        print(f"≡اّج Creating new user: {user_id}")
        db.add(models.User(id=user_id))
        db.commit()
    else:
        print(f"≡اّج User exists: {user_id}")

    verifier, challenge = generate_pkce()
    state = new_state()
    # store BOTH verifier and user_id
    put_state(state, verifier, user_id)
    
    auth_url = build_auth_url(state, challenge)
    print(f"≡ا¤ù Generated OAuth URL (first 100 chars): {auth_url[:100]}...")
    print(f"≡ا¤ù Redirecting to Twitter OAuth")
    print("=" * 80)
    
    return RedirectResponse(auth_url)


@app.get("/v1/oauth/x/callback")
async def x_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    request: Request = None,
):
    print("=" * 80)
    print("≡ا¤ù OAuth Callback Received")
    print(f"   Code: {'Present' if code else 'Missing'}")
    if code:
        print(f"   Code (first 20 chars): {code[:20]}...")
    print(f"   State: {state if state else 'Missing'}")
    print(f"   Error: {error if error else 'None'}")
    print("=" * 80)
    
    # Handle OAuth errors from Twitter
    if error:
        print(f"ظإî OAuth error from Twitter: {error}")
        app_redirect_url = f"ibtikar://oauth/callback?error={error}"
        print(f"≡ا¤ Redirecting to app (error): {app_redirect_url}")
        return RedirectResponse(url=app_redirect_url)
    
    if not code or not state:
        print("ظإî Missing code or state")
        raise HTTPException(status_code=400, detail="Missing code/state")

    state_data = pop_state(state)
    if not state_data:
        print("ظإî State expired or invalid")
        raise HTTPException(status_code=400, detail="State expired/invalid")

    code_verifier = state_data["verifier"]
    user_id = int(state_data["user_id"])

    print(f"ظ£à State validated, user_id: {user_id}")
    print("≡ا¤ Exchanging code for token...")

    try:
    token = await exchange_code_for_token(code, code_verifier)
        print("ظ£à Token exchange successful")
    except Exception as e:
        print(f"ظإî Token exchange failed: {e}")
        app_redirect_url = f"ibtikar://oauth/callback?error=token_exchange_failed"
        print(f"≡ا¤ Redirecting to app (error): {app_redirect_url}")
        return RedirectResponse(url=app_redirect_url)

    # ensure this user exists
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        print(f"≡اّج Creating new user: {user_id}")
        db.add(models.User(id=user_id))
        db.commit()
    else:
        print(f"≡اّج User exists: {user_id}")

    existing = db.query(models.XToken).filter(models.XToken.user_id == user_id).first()
    if not existing:
        print("≡اْ╛ Creating new XToken record")
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
    else:
        print("≡اْ╛ Updating existing XToken record")
        existing.access_token = enc(token.get("access_token", ""))
        existing.refresh_token = (
            enc(token.get("refresh_token", ""))
            if token.get("refresh_token")
            else None
        )
        existing.scope = token.get("scope")
        existing.token_type = token.get("token_type")
        existing.expires_in = token.get("expires_in")

    db.commit()
    print("ظ£à Database updated successfully")
    
    # Check if this is a web request (by checking Referer or User-Agent)
    is_web_request = False
    if request:
        referer = request.headers.get("referer", "")
        user_agent = request.headers.get("user-agent", "").lower()
        # Check if referer is a web URL or user-agent indicates browser
        if referer and ("http://" in referer or "https://" in referer):
            is_web_request = True
            print(f"≡اî Web request detected (Referer: {referer})")
        elif "mozilla" in user_agent or "chrome" in user_agent or "safari" in user_agent:
            is_web_request = True
            print(f"≡اî Web request detected (User-Agent: {user_agent[:50]}...)")
    
    # For web requests, redirect directly to the web URL with callback params
    if is_web_request:
        # Try to get the origin from Referer, or use a default
        web_origin = "http://localhost:8081"  # Default for local dev
        if request and request.headers.get("referer"):
            try:
                from urllib.parse import urlparse
                parsed = urlparse(request.headers.get("referer"))
                web_origin = f"{parsed.scheme}://{parsed.netloc}"
            except:
                pass
        web_redirect_url = f"{web_origin}?success=true&user_id={user_id}"
        print(f"≡ا¤ Redirecting to web app: {web_redirect_url}")
        return RedirectResponse(url=web_redirect_url)
    
    # Return HTML page that tries to open app AND shows success message
    # This works even if deep links don't work
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login Successful - Ibtikar</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }}
            .container {{
                text-align: center;
                padding: 40px;
                background: rgba(0, 0, 0, 0.3);
                border-radius: 20px;
                max-width: 500px;
            }}
            .success-icon {{
                font-size: 80px;
                margin-bottom: 20px;
            }}
            h1 {{
                font-size: 32px;
                margin-bottom: 10px;
            }}
            p {{
                font-size: 18px;
                margin-bottom: 30px;
                opacity: 0.9;
            }}
            .status {{
                background: rgba(255, 255, 255, 0.2);
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">ظ£à</div>
            <h1>Login Successful!</h1>
            <p>Your Twitter account has been linked.</p>
            <div class="status">
                <p><strong>User ID:</strong> {user_id}</p>
                <p><strong>Status:</strong> Account Linked</p>
            </div>
            <p style="font-size: 14px; opacity: 0.8;">
                You can now close this page and return to the app.<br>
                The app will automatically detect your login.
            </p>
        </div>
        <script>
            // Try to open the app via deep link
            const deepLink = "ibtikar://oauth/callback?success=true&user_id={user_id}";
            
            // Try opening the deep link
            setTimeout(() => {{
                window.location.href = deepLink;
            }}, 500);
            
            // Also log for debugging
            console.log("Attempting to open:", deepLink);
        </script>
    </body>
    </html>
    """
    
    print(f"≡ا¤ Returning success page for user_id: {user_id}")
    print("=" * 80)
    return HTMLResponse(content=html_content)


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
    ظ£Timeline-liteظإ: pulls recent posts from accounts the user follows.
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

    preds = await analyze_texts([p.text for p in posts])

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

    return AnalysisResponse(
        items=items,
        harmful_count=hc,
        safe_count=sc,
        unknown_count=uc,
    )

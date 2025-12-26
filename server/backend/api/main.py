from datetime import datetime
import time

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.exceptions import NotFound
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

# Log that we're creating the app
import sys
print("CREATING FASTAPI APP", file=sys.stderr, flush=True)

app = FastAPI(title="IbtikarAI Backend", version="0.2.0")
print("FASTAPI APP CREATED", file=sys.stderr, flush=True)

# CRITICAL: Define routes IMMEDIATELY after app creation - simplest possible approach
print("REGISTERING CRITICAL ROUTES", file=sys.stderr, flush=True)

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint"""
    print("ROOT CALLED", file=sys.stderr, flush=True)
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Ibtikar Backend API</title></head>
<body><h1>Ibtikar Backend API</h1><p>Service is running.</p>
<p><a href="/health">Health Check</a> | <a href="/privacy-policy.html">Privacy Policy</a> | <a href="/delete-account.html">Delete Account</a></p>
</body></html>"""

@app.get("/privacy-policy.html", response_class=HTMLResponse)
async def privacy_policy():
    """Privacy Policy page"""
    print("PRIVACY POLICY CALLED", file=sys.stderr, flush=True)
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Privacy Policy - Ibtikar</title></head>
<body><h1>Privacy Policy for Ibtikar</h1><p>Last Updated: January 2025</p>
<p>Ibtikar ("we," "our," or "us") operated by <strong>Ibtikar Development</strong> (Account ID: 8344367188917813700) is committed to protecting your privacy.</p>
<p><strong>Email:</strong> support@ibtikar.app</p>
<p><a href="delete-account.html">Request Account Deletion</a></p>
</body></html>"""

@app.get("/delete-account.html", response_class=HTMLResponse)
async def delete_account():
    """Delete Account page"""
    print("DELETE ACCOUNT CALLED", file=sys.stderr, flush=True)
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Delete Account - Ibtikar</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { color: #D90000; border-bottom: 3px solid #F6DE55; padding-bottom: 10px; }
        h2 { color: #00A3A3; margin-top: 30px; }
        .warning { background-color: #FFF3CD; border: 2px solid #FFC107; border-radius: 8px; padding: 15px; margin: 20px 0; }
        .steps { background-color: #FFFFFF; border: 2px solid #00A3A3; border-radius: 8px; padding: 20px; margin: 20px 0; }
        .data-list { background-color: #E8F5E9; border-left: 4px solid #38B000; padding: 15px; margin: 15px 0; }
        .contact { background-color: #FFFFFF; padding: 20px; border-radius: 8px; border: 2px solid #00A3A3; margin-top: 30px; }
        strong { color: #D90000; }
    </style>
</head>
<body>
    <h1>Delete Your Ibtikar Account</h1>
    <p><strong>App Name:</strong> Ibtikar</p>
    <p><strong>Developer:</strong> Ibtikar Development</p>
    <div class="warning">
        <strong>⚠️ Important:</strong> Deleting your account is <strong>permanent and irreversible</strong>. All your data will be permanently deleted.
    </div>
    <h2>How to Request Account Deletion</h2>
    <div class="steps">
        <p><strong>Follow these steps to delete your Ibtikar account:</strong></p>
        <ol>
            <li>Open the <strong>Ibtikar</strong> app on your device</li>
            <li>Navigate to your profile settings</li>
            <li>Tap "Logout" to disconnect your account</li>
            <li><strong>Email us at support@ibtikar.app</strong> with the subject line: <strong>"Account Deletion Request"</strong></li>
            <li>Include your Twitter/X username in the email</li>
            <li>Confirm that you want to permanently delete your account</li>
        </ol>
        <p><strong>Email Address:</strong> <a href="mailto:support@ibtikar.app?subject=Account%20Deletion%20Request">support@ibtikar.app</a></p>
    </div>
    <h2>Data That Will Be Deleted</h2>
    <div class="data-list">
        <p>When you delete your <strong>Ibtikar</strong> account, the following data will be <strong>permanently removed</strong>:</p>
        <ul>
            <li><strong>Account Information:</strong> Your Ibtikar user account, Twitter/X user ID, username, display name, profile image URL</li>
            <li><strong>Authentication Data:</strong> All Twitter/X OAuth tokens (encrypted) and connection information</li>
            <li><strong>Content Data:</strong> All analyzed posts, tweets, post content, metadata, and language classifications</li>
            <li><strong>Analysis Results:</strong> All AI classification results (harmful/safe/unknown labels), confidence scores, and aggregate statistics</li>
            <li><strong>App Data:</strong> Your activation status, preferences, settings, and error logs</li>
        </ul>
    </div>
    <h2>Data Retention Period</h2>
    <p><strong>Deletion Timeline:</strong></p>
    <ul>
        <li><strong>Immediate:</strong> Your account data is deleted immediately from our active databases upon confirmation</li>
        <li><strong>Within 30 Days:</strong> All backup copies are permanently deleted</li>
        <li><strong>No Retention:</strong> We do not retain any of your data after deletion</li>
        <li><strong>No Recovery:</strong> Once deleted, your data cannot be recovered or restored</li>
    </ul>
    <p><strong>Additional Retention Period:</strong> None. All data is permanently deleted within 30 days of your deletion request.</p>
    <h2>Contact Information</h2>
    <div class="contact">
        <p><strong>App Name:</strong> Ibtikar</p>
        <p><strong>Developer:</strong> Ibtikar Development</p>
        <p><strong>Email:</strong> <a href="mailto:support@ibtikar.app?subject=Account%20Deletion%20Request">support@ibtikar.app</a></p>
        <p><strong>Subject:</strong> Account Deletion Request</p>
        <p><strong>Response Time:</strong> We aim to respond within 48 hours and complete deletion within 7 business days.</p>
    </div>
    <p style="margin-top: 40px; text-align: center;">
        <a href="privacy-policy.html">View Privacy Policy</a> | 
        <a href="mailto:support@ibtikar.app?subject=Account%20Deletion%20Request">Contact Support</a>
    </p>
</body>
</html>"""

print("CRITICAL ROUTES REGISTERED", file=sys.stderr, flush=True)
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Delete Account - Ibtikar</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; color: #333; background-color: #FAFAFA; }
        h1 { color: #D90000; border-bottom: 3px solid #F6DE55; padding-bottom: 10px; }
        h2 { color: #00A3A3; margin-top: 30px; }
        .app-info { background-color: #E3F2FD; border-left: 4px solid #2196F3; padding: 15px; margin: 20px 0; font-size: 18px; }
        .warning { background-color: #FFF3CD; border: 2px solid #FFC107; border-radius: 8px; padding: 15px; margin: 20px 0; }
        .steps { background-color: #FFFFFF; border: 2px solid #00A3A3; border-radius: 8px; padding: 20px; margin: 20px 0; }
        .steps ol { padding-left: 20px; }
        .steps li { margin: 10px 0; font-size: 16px; }
        .data-list { background-color: #E8F5E9; border-left: 4px solid #38B000; padding: 15px; margin: 15px 0; }
        .contact { background-color: #FFFFFF; padding: 20px; border-radius: 8px; border: 2px solid #00A3A3; margin-top: 30px; }
        strong { color: #D90000; }
        .button { display: inline-block; background-color: #D90000; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; margin: 10px 5px; font-weight: bold; }
        .button:hover { background-color: #B80000; }
    </style>
</head>
<body>
    <div class="app-info">
        <p><strong>App Name:</strong> Ibtikar</p>
        <p><strong>Developer:</strong> Ibtikar Development</p>
    </div>

    <h1>Delete Your Ibtikar Account</h1>
    <p>This page explains how to delete your <strong>Ibtikar</strong> account and all associated data. This process is permanent and cannot be undone.</p>

    <div class="warning">
        <strong>⚠️ Important Warning:</strong> Deleting your <strong>Ibtikar</strong> account is <strong>permanent and irreversible</strong>. All your data will be permanently deleted and cannot be recovered. Please read this page carefully before proceeding.
    </div>

    <h2>How to Request Account Deletion</h2>
    <div class="steps">
        <p><strong>Follow these steps to delete your Ibtikar account:</strong></p>
        <ol>
            <li><strong>Open the Ibtikar app</strong> on your Android or iOS device</li>
            <li><strong>Navigate to your profile</strong> or main screen</li>
            <li><strong>Find the "Logout" button</strong> (typically located in the top-right corner)</li>
            <li><strong>Tap "Logout"</strong> - This will log you out and clear your local app data</li>
            <li><strong>Email us at <a href="mailto:support@ibtikar.app?subject=Account%20Deletion%20Request">support@ibtikar.app</a></strong> with the subject line: <strong>"Account Deletion Request"</strong></li>
            <li><strong>Include your Twitter/X username</strong> in the email</li>
            <li><strong>Confirm that you want to permanently delete your account</strong></li>
        </ol>
        <p style="margin-top: 20px; font-size: 18px;"><strong>Email Address:</strong> <a href="mailto:support@ibtikar.app?subject=Account%20Deletion%20Request" style="color: #D90000; font-weight: bold;">support@ibtikar.app</a></p>
    </div>

    <h2>Types of Data That Will Be Deleted</h2>
    <div class="data-list">
        <p>When you delete your <strong>Ibtikar</strong> account, the following data will be <strong>permanently removed</strong> from our systems:</p>
        <ul>
            <li><strong>Account Information:</strong> Your Ibtikar user account, Twitter/X user ID, username, display name, and profile image URL</li>
            <li><strong>Authentication Data:</strong> All Twitter/X OAuth access tokens (encrypted), refresh tokens (encrypted), and all OAuth connection information</li>
            <li><strong>Content Data:</strong> All analyzed posts and tweets from your feed, post content, text, metadata, post IDs, author IDs, timestamps, and language classifications</li>
            <li><strong>Analysis Results:</strong> All AI classification results (harmful/safe/unknown labels), confidence scores for each analysis, analysis timestamps, and aggregate statistics and summaries</li>
            <li><strong>App Data:</strong> Your activation status and preferences, app settings and configurations, and error logs associated with your account</li>
        </ul>
    </div>

    <h2>Data Retention Period</h2>
    <p><strong>Deletion Timeline:</strong></p>
    <ul>
        <li><strong>Immediate:</strong> Your account data is deleted immediately from our active databases upon confirmation of your deletion request</li>
        <li><strong>Within 30 Days:</strong> All backup copies are permanently deleted</li>
        <li><strong>No Retention:</strong> We do not retain any of your data after deletion</li>
        <li><strong>No Recovery:</strong> Once deleted, your data cannot be recovered or restored</li>
    </ul>
    <p><strong>Additional Retention Period:</strong> None. All data is permanently deleted within 30 days of your deletion request.</p>

    <h2>Contact Information</h2>
    <div class="contact">
        <p>If you need assistance deleting your account, have questions about the deletion process, or want to verify that your account has been deleted, please contact us:</p>
        <p><strong>App Name:</strong> Ibtikar</p>
        <p><strong>Developer:</strong> Ibtikar Development</p>
        <p><strong>Email:</strong> <a href="mailto:support@ibtikar.app?subject=Account%20Deletion%20Request">support@ibtikar.app</a></p>
        <p><strong>Subject:</strong> Account Deletion Request</p>
        <p><strong>Account ID:</strong> 8344367188917813700</p>
        <p style="margin-top: 15px;"><strong>Response Time:</strong> We aim to respond to deletion requests within 48 hours and complete deletion within 7 business days.</p>
    </div>

    <p style="margin-top: 40px; text-align: center;">
        <a href="privacy-policy.html" class="button" style="background-color: #00A3A3;">View Privacy Policy</a>
        <a href="mailto:support@ibtikar.app?subject=Account%20Deletion%20Request" class="button">Contact Support</a>
    </p>

    <p style="text-align: center; margin-top: 20px; color: #666;">
        <small>Last Updated: January 2025</small>
    </p>
</body>
</html>""")

# Wrap init_db in try/except to prevent import errors from blocking route registration
try:
    init_db()  # create tables on startup (local dev)
except Exception as e:
    import sys
    print(f"WARNING: init_db() failed: {e}", file=sys.stderr, flush=True)
    # Don't fail the entire app if DB init fails

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

# Load HTML content at startup for reliable serving
_privacy_policy_html = None
_delete_account_html = None

def _load_html_content():
    """Load HTML files at startup, with fallback to embedded content"""
    global _privacy_policy_html, _delete_account_html
    
    # Try to load privacy policy
    possible_files = [
        static_dir / "privacy-policy.html",
        Path(os.getcwd()) / "server" / "static" / "privacy-policy.html",
        Path(os.getcwd()) / "static" / "privacy-policy.html",
        Path(__file__).parent.parent.parent / "static" / "privacy-policy.html",
    ]
    
    for file_path in possible_files:
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    _privacy_policy_html = f.read()
                logger.info(f"Loaded privacy-policy.html from: {file_path.absolute()}")
                break
            except Exception as e:
                logger.warning(f"Failed to read {file_path}: {e}")
    
    # Try to load delete account page
    possible_files = [
        static_dir / "delete-account.html",
        Path(os.getcwd()) / "server" / "static" / "delete-account.html",
        Path(os.getcwd()) / "static" / "delete-account.html",
        Path(__file__).parent.parent.parent / "static" / "delete-account.html",
    ]
    
    for file_path in possible_files:
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    _delete_account_html = f.read()
                logger.info(f"Loaded delete-account.html from: {file_path.absolute()}")
                break
            except Exception as e:
                logger.warning(f"Failed to read {file_path}: {e}")
    
    # If files weren't loaded, use embedded fallback (will be set in routes)
    if not _privacy_policy_html:
        logger.warning("Privacy policy file not found, will use embedded fallback")
    if not _delete_account_html:
        logger.warning("Delete account file not found, will use embedded fallback")

# Load HTML content at module import
_load_html_content()

# Add startup event to log route registration
@app.on_event("startup")
async def startup_event():
    """Log startup information and verify routes"""
    import sys
    # Use print to ensure it shows up in logs
    print("=" * 80, file=sys.stderr)
    print("Ibtikar Backend API Starting", file=sys.stderr)
    print(f"Current working directory: {os.getcwd()}", file=sys.stderr)
    print(f"__file__ location: {__file__}", file=sys.stderr)
    print(f"Static directory: {static_dir}", file=sys.stderr)
    print(f"Privacy policy HTML loaded: {_privacy_policy_html is not None}", file=sys.stderr)
    print(f"Delete account HTML loaded: {_delete_account_html is not None}", file=sys.stderr)
    # List all registered routes
    print("Registered routes:", file=sys.stderr)
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            print(f"  {list(route.methods)} {route.path}", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    logger.info("=" * 80)
    logger.info("Ibtikar Backend API Starting")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"__file__ location: {__file__}")
    logger.info(f"Static directory: {static_dir}")
    logger.info(f"Privacy policy HTML loaded: {_privacy_policy_html is not None}")
    logger.info(f"Delete account HTML loaded: {_delete_account_html is not None}")
    logger.info("=" * 80)

# Routes are already defined at the top of the file - no duplicates needed

@app.get("/test")
async def test_endpoint():
    """Simple test endpoint to verify the app is working"""
    return {
        "status": "ok",
        "message": "API is working",
        "routes": {
            "root": "/",
            "privacy_policy": "/privacy-policy.html",
            "delete_account": "/delete-account.html",
            "health": "/health"
        }
    }

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

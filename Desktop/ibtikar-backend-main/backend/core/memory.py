import time, secrets
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.db.models import OAuthState

def new_state() -> str:
    return secrets.token_urlsafe(24)

def put_state(state: str, verifier: str, user_id: int, ttl_seconds: int = 600, db: Session = None) -> None:
    """
    Store OAuth state in database instead of memory.
    This allows the state to persist across restarts and work with multiple instances.
    """
    if db is None:
        # Fallback to in-memory for backwards compatibility (should not happen in production)
        import warnings
        warnings.warn("put_state called without database session, using in-memory storage")
        _state_store[state] = {"verifier": verifier, "user_id": int(user_id), "exp": int(time.time()) + ttl_seconds}
        return
    
    try:
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        
        # Store in database
        db_state = OAuthState(
            state=state,
            code_verifier=verifier,
            user_id=int(user_id),
            expires_at=expires_at
        )
        db.add(db_state)
        db.commit()
        
        print(f"✅ Stored OAuth state in database: {state[:10]}... (expires at {expires_at})")
        
        # Also clean up expired states while we're at it
        cleanup_expired_states(db)
    except Exception as e:
        print(f"❌ Error storing OAuth state in database: {e}")
        print(f"   Falling back to in-memory storage for state: {state[:10]}...")
        import traceback
        traceback.print_exc()
        db.rollback()
        # Fallback to in-memory
        _state_store[state] = {"verifier": verifier, "user_id": int(user_id), "exp": int(time.time()) + ttl_seconds}

def pop_state(state: str, db: Session = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve and delete OAuth state from database.
    Returns None if state is invalid or expired.
    """
    if db is None:
        # Fallback to in-memory for backwards compatibility (should not happen in production)
        import warnings
        warnings.warn("pop_state called without database session, using in-memory storage")
        item = _state_store.pop(state, None)
        if not item:
            return None
        if item["exp"] < time.time():
            return None
        return item
    
    try:
        # Get state from database
        db_state = db.query(OAuthState).filter(OAuthState.state == state).first()
        
        if not db_state:
            print(f"⚠️ OAuth state not found in database: {state[:10]}...")
            # Also check in-memory fallback
            item = _state_store.pop(state, None)
            if item and item["exp"] >= time.time():
                print(f"   Found state in-memory fallback")
                return {"verifier": item["verifier"], "user_id": item["user_id"]}
            return None
        
        # Check if expired
        if db_state.expires_at < datetime.utcnow():
            print(f"⚠️ OAuth state expired: {state[:10]}... (expired at {db_state.expires_at})")
            db.delete(db_state)
            db.commit()
            return None
        
        # Extract data and delete state
        result = {
            "verifier": db_state.code_verifier,
            "user_id": db_state.user_id,
        }
        
        # Delete the state (one-time use)
        db.delete(db_state)
        db.commit()
        
        print(f"✅ Retrieved and deleted OAuth state from database: {state[:10]}...")
        return result
        
    except Exception as e:
        print(f"❌ Error retrieving OAuth state from database: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        
        # Fallback to in-memory
        item = _state_store.pop(state, None)
        if item and item["exp"] >= time.time():
            print(f"   Using in-memory fallback for state: {state[:10]}...")
            return {"verifier": item["verifier"], "user_id": item["user_id"]}
        return None

def cleanup_expired_states(db: Session) -> None:
    """Clean up expired OAuth states from database."""
    try:
        expired_count = db.query(OAuthState).filter(OAuthState.expires_at < datetime.utcnow()).delete()
        if expired_count > 0:
            db.commit()
            print(f"🧹 Cleaned up {expired_count} expired OAuth states")
    except Exception as e:
        # Don't fail the OAuth flow if cleanup fails
        print(f"⚠️ Failed to cleanup expired states: {e}")
        db.rollback()

# Keep in-memory fallback for backwards compatibility (not recommended for production)
_state_store: Dict[str, Dict[str, Any]] = {}

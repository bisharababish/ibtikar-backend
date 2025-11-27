import base64, hashlib, os
from typing import Dict, Any
import httpx
from backend.core.config import settings

AUTH_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"

def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")

def generate_pkce() -> tuple[str, str]:
    verifier = _b64url(os.urandom(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge

def _normalize_redirect_uri(uri: str) -> str:
    """Normalize redirect URI - remove trailing slash, ensure consistent format."""
    uri = str(uri).rstrip("/")
    return uri

def build_auth_url(state: str, code_challenge: str, force_login: bool = True) -> str:
    """
    Build Twitter OAuth authorization URL.
    ALWAYS forces login screen (username/password entry) to allow account switching.
    
    Args:
        state: OAuth state parameter
        code_challenge: PKCE code challenge
        force_login: If True, forces user to re-enter credentials (allows account switching)
    
    Note: X_REDIRECT_URI environment variable MUST be set to:
          https://ibtikar-backend.onrender.com/v1/oauth/x/callback
          (NOT ibtikar://oauth/callback - that's the app deep link)
    """
    redirect_uri = _normalize_redirect_uri(settings.X_REDIRECT_URI)
    
    # Verify redirect URI is the backend URL, not app deep link
    if not redirect_uri.startswith("https://"):
        print(f"⚠️ WARNING: X_REDIRECT_URI should be backend URL, not app deep link!")
        print(f"   Current: {redirect_uri}")
        print(f"   Expected: https://ibtikar-backend.onrender.com/v1/oauth/x/callback")
    params = {
        "response_type": "code",
        "client_id": settings.X_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": settings.X_SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    
    # CRITICAL: Force login screen (username/password) every time
    # Use BOTH force_login=true AND prompt=login for maximum reliability
    # force_login=true forces Twitter to show login screen even if user is logged in
    # prompt=login also forces re-authentication
    params["force_login"] = "true"
    params["prompt"] = "login"  # Additional parameter to force login screen
    
    # Add multiple unique parameters to prevent ANY caching
    # This ensures Twitter treats each request as completely new
    import time
    import random
    timestamp = int(time.time() * 1000)
    random_num = random.randint(10000, 99999)
    cache_bust = f"{timestamp}{random_num}"
    
    params["_t"] = cache_bust
    params["_"] = cache_bust
    params["_nocache"] = cache_bust
    params["_r"] = str(random.randint(100000, 999999))  # Additional random
    
    qp = httpx.QueryParams(params)
    auth_url = f"{AUTH_URL}?{qp}"
    
    # Verify force_login and prompt are in the URL
    if "force_login=true" not in auth_url:
        print("⚠️ WARNING: force_login=true not found in OAuth URL!")
    else:
        print("✅ Verified: force_login=true is in OAuth URL")
    
    if "prompt=login" not in auth_url:
        print("⚠️ WARNING: prompt=login not found in OAuth URL!")
    else:
        print("✅ Verified: prompt=login is in OAuth URL")
    
    print(f"🔗 Built OAuth URL (will show SIGN IN page every time)")
    print(f"   URL: {auth_url}")
    print(f"   force_login=true + prompt=login ensures login screen (username/password entry)")
    return auth_url



async def exchange_code_for_token(code: str, code_verifier: str) -> Dict[str, Any]:
    # Normalize redirect URI to match exactly what was used in auth URL
    redirect_uri = _normalize_redirect_uri(settings.X_REDIRECT_URI)
    client_id = settings.X_CLIENT_ID
    client_secret = settings.X_CLIENT_SECRET
    
    # Twitter OAuth 2.0 requires Basic Authentication for token exchange
    # Format: base64(client_id:client_secret)
    credentials = f"{client_id}:{client_secret}"
    auth_header = base64.b64encode(credentials.encode()).decode()
    
    # Log for debugging (don't log sensitive data in production)
    print(f"🔄 Token exchange request:")
    print(f"   Client ID: {client_id[:10]}...")
    print(f"   Redirect URI: {redirect_uri}")
    print(f"   Code: {code[:20]}...")
    print(f"   Code verifier length: {len(code_verifier)}")
    print(f"   Using Basic Auth: Yes")
    
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.post(
                TOKEN_URL,
                data=data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {auth_header}",
                },
            )
            if not r.is_success:
                error_text = r.text
                error_json = None
                try:
                    error_json = r.json()
                except:
                    pass
                
                print(f"❌ Token exchange failed with status {r.status_code}")
                print(f"   Response text: {error_text}")
                if error_json:
                    print(f"   Response JSON: {error_json}")
                print(f"   Request redirect_uri: {redirect_uri}")
                print(f"   Request client_id: {client_id[:10]}...")
                print(f"   Request grant_type: authorization_code")
                print(f"   Code length: {len(code)}")
                print(f"   Code verifier length: {len(code_verifier)}")
                
                # Extract specific error if available
                error_msg = error_text
                if error_json and "error" in error_json:
                    error_msg = f"{error_json.get('error')}: {error_json.get('error_description', '')}"
                
                raise Exception(f"Token exchange failed: {r.status_code} - {error_msg}")
            return r.json()
        except httpx.HTTPError as e:
            print(f"❌ HTTP error during token exchange: {str(e)}")
            raise Exception(f"Token exchange HTTP error: {str(e)}")

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
    ALWAYS forces login screen to allow account switching.
    
    Args:
        state: OAuth state parameter
        code_challenge: PKCE code challenge
        force_login: If True, forces user to re-enter credentials (allows account switching)
    """
    redirect_uri = _normalize_redirect_uri(settings.X_REDIRECT_URI)
    params = {
        "response_type": "code",
        "client_id": settings.X_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": settings.X_SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    
    # CRITICAL: Force login screen every time to allow account switching
    # Twitter OAuth 2.0: force_login parameter forces login screen
    # This is ESSENTIAL for allowing users to switch accounts
    params["force_login"] = "true"
    
    # Add unique timestamp to prevent any URL caching
    import time
    import random
    cache_bust = str(int(time.time() * 1000)) + str(random.randint(1000, 9999))
    params["_t"] = cache_bust
    
    qp = httpx.QueryParams(params)
    auth_url = f"{AUTH_URL}?{qp}"
    print(f"🔗 Built OAuth URL with force_login=true: {auth_url}")
    print(f"   Parameters: force_login=true, cache_bust={cache_bust}")
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

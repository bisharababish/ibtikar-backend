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

def build_auth_url(state: str, code_challenge: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.X_CLIENT_ID,
        "redirect_uri": str(settings.X_REDIRECT_URI),
        "scope": settings.X_SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    qp = httpx.QueryParams(params)
    return f"{AUTH_URL}?{qp}"

async def exchange_code_for_token(code: str, code_verifier: str) -> Dict[str, Any]:
    redirect_uri = str(settings.X_REDIRECT_URI)
    client_id = settings.X_CLIENT_ID
    
    # Log for debugging (don't log sensitive data in production)
    print(f"🔄 Token exchange request:")
    print(f"   Client ID: {client_id[:10]}...")
    print(f"   Redirect URI: {redirect_uri}")
    print(f"   Code: {code[:20]}...")
    
    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if not r.is_success:
            error_text = r.text
            print(f"❌ Token exchange failed with status {r.status_code}")
            print(f"   Response: {error_text}")
            print(f"   Request redirect_uri: {redirect_uri}")
            print(f"   Request client_id: {client_id[:10]}...")
            raise Exception(f"Token exchange failed: {r.status_code} - {error_text}")
        return r.json()

import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from backend.config import ENABLE_KEYCLOAK, KEYCLOAK_URL, KEYCLOAK_CLIENT_ID

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    """
    Middleware dependency to get current authenticated user.
    If ENABLE_KEYCLOAK is False, returns a default local user dict.
    If ENABLE_KEYCLOAK is True, validates Keycloak JWT token.
    """
    if not ENABLE_KEYCLOAK:
        return {
            "sub": "local-user-id",
            "preferred_username": "local_user",
            "email": "user@airgap.local",
            "authenticated": False,
            "mode": "keycloak_disabled"
        }

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        from jose import jwt
        import requests

        # Fetch Keycloak public key / OIDC certs
        jwks_url = f"{KEYCLOAK_URL}/protocol/openid-connect/certs"
        jwks_res = requests.get(jwks_url, timeout=5)
        jwks = jwks_res.json()

        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        for key in jwks.get("keys", []):
            if key["kid"] == unverified_header.get("kid"):
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
                break

        if rsa_key:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                audience=KEYCLOAK_CLIENT_ID,
                issuer=KEYCLOAK_URL
            )
            payload["authenticated"] = True
            payload["mode"] = "keycloak_enabled"
            return payload

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature or key ID"
        )
    except Exception as e:
        logger.error(f"Keycloak token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}"
        )

"""Authentification simple des employés de la banque (login + jeton signé).

Volontairement minimal (pas de base d'utilisateurs, pas de refresh token) :
les comptes viennent de la variable d'environnement PLATFORM_USERS
("utilisateur:mot_de_passe,autre:mot_de_passe") et le jeton est un HMAC
signé avec PLATFORM_SECRET. L'important : l'authentification est vérifiée
côté API sur chaque endpoint protégé (voir `current_user`), pas seulement
masquée dans l'interface — le service est joignable depuis Internet sur
Komodo et expose des actions destructives (suppression de lignes, rollback,
redéploiement).

ATTENTION : les valeurs par défaut ci-dessous ne sont là que pour la démo
locale ; à surcharger dans l'Environment de la stack Komodo (même réserve
que pour MinIO/Grafana, voir data/README.md).
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

TOKEN_TTL_SECONDS = 8 * 3600  # une journée de travail

DEFAULT_USERS = "admin:changeme"

_bearer = HTTPBearer(auto_error=False)

# Secret par défaut aléatoire au démarrage du process : les jetons émis
# avant un redémarrage deviennent invalides (acceptable pour un outil interne),
# mais mieux vaut fixer PLATFORM_SECRET pour survivre aux redéploiements.
_fallback_secret = secrets.token_hex(32)
_warned_about_secret = False


def _secret() -> bytes:
    global _warned_about_secret
    configured = os.environ.get("PLATFORM_SECRET")
    if not configured and not _warned_about_secret:
        logger.warning("PLATFORM_SECRET non défini : secret éphémère utilisé (jetons perdus au redémarrage).")
        _warned_about_secret = True
    return (configured or _fallback_secret).encode()


def load_users() -> dict[str, str]:
    raw = os.environ.get("PLATFORM_USERS", DEFAULT_USERS)
    users = {}
    for entry in raw.split(","):
        name, sep, password = entry.strip().partition(":")
        if sep and name:
            users[name] = password
    return users


def verify_credentials(username: str, password: str) -> bool:
    expected = load_users().get(username)
    # Comparaison à temps constant, y compris quand l'utilisateur n'existe pas.
    matches = hmac.compare_digest((expected or "\0").encode(), password.encode())
    return matches and expected is not None


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def create_token(username: str, now: float | None = None) -> str:
    payload = _b64(json.dumps({"sub": username, "exp": int((now or time.time()) + TOKEN_TTL_SECONDS)}).encode())
    signature = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def decode_token(token: str, now: float | None = None) -> str | None:
    """Renvoie le nom d'utilisateur si le jeton est valide et non expiré."""
    payload, _, signature = token.partition(".")
    expected = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    if not payload or not hmac.compare_digest(signature, expected):
        return None
    try:
        claims = json.loads(_unb64(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if claims.get("exp", 0) < (now or time.time()):
        return None
    return claims.get("sub")


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    """Dépendance FastAPI : nom de l'employé authentifié, sinon 401."""
    username = decode_token(credentials.credentials) if credentials else None
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username

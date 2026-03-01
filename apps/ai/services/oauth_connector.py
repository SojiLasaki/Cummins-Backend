import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from django.core.cache import cache


CACHE_PREFIX = "felix:mcp_oauth:"
PENDING_TTL_SECONDS = 900
FINAL_TTL_SECONDS = 300


@dataclass
class OAuthStartResult:
    ok: bool
    authorization_url: str = ""
    state: str = ""
    expires_in: int = PENDING_TTL_SECONDS
    error: str = ""
    hint: str = ""


@dataclass
class OAuthStatusResult:
    ok: bool
    status: str
    error: str = ""
    has_access_token: bool = False


@dataclass
class OAuthCompleteResult:
    ok: bool
    adapter_id: int | None = None
    access_token: str = ""
    refresh_token: str = ""
    token_type: str = ""
    expires_in: int | None = None
    scope: str = ""
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    error: str = ""


def _cache_key(state: str) -> str:
    return f"{CACHE_PREFIX}{state}"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _to_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _normalize_scopes(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.replace(",", " ").split() if part.strip()]
    return []


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _json_get(url: str, timeout: int = 10) -> dict[str, Any] | None:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "FixItFelix-OAuth/1.0",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


def _build_well_known_urls(base: str) -> list[str]:
    normalized = str(base or "").strip().rstrip("/")
    if not normalized:
        return []
    return [
        f"{normalized}/.well-known/openid-configuration",
        f"{normalized}/.well-known/oauth-authorization-server",
    ]


def _extract_origin_and_path(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    path = (parsed.path or "").rstrip("/")
    return origin, path


def _discover_oauth_endpoints(mcp_url: str, auth_config: dict[str, Any]) -> tuple[str, str, str]:
    explicit_authorize = str(
        auth_config.get("authorize_url")
        or auth_config.get("authorization_endpoint")
        or ""
    ).strip()
    explicit_token = str(
        auth_config.get("token_url")
        or auth_config.get("token_endpoint")
        or ""
    ).strip()
    if explicit_authorize and explicit_token:
        return explicit_authorize, explicit_token, ""

    candidates: list[str] = []
    issuer = str(auth_config.get("issuer_url") or auth_config.get("authorization_server") or "").strip()
    if issuer:
        candidates.append(issuer)

    origin, path = _extract_origin_and_path(mcp_url)
    if origin:
        protected_candidates = [f"{origin}/.well-known/oauth-protected-resource"]
        if path:
            protected_candidates.append(f"{origin}/.well-known/oauth-protected-resource{path}")

        for protected_url in _dedupe(protected_candidates):
            metadata = _json_get(protected_url)
            if not metadata:
                continue
            servers = metadata.get("authorization_servers")
            if isinstance(servers, list):
                candidates.extend(str(item).strip() for item in servers if str(item).strip())
            single_server = metadata.get("authorization_server")
            if isinstance(single_server, str) and single_server.strip():
                candidates.append(single_server.strip())

        candidates.append(origin)

    for server in _dedupe(candidates):
        for metadata_url in _build_well_known_urls(server):
            metadata = _json_get(metadata_url)
            if not metadata:
                continue
            authorization_endpoint = str(metadata.get("authorization_endpoint") or "").strip()
            token_endpoint = str(metadata.get("token_endpoint") or "").strip()
            if authorization_endpoint and token_endpoint:
                return authorization_endpoint, token_endpoint, ""

    return "", "", (
        "Could not discover OAuth endpoints for this MCP server. "
        "Provide Authorization URL and Token URL in adapter settings."
    )


def start_oauth_flow(
    *,
    adapter_id: int,
    mcp_url: str,
    auth_config: dict[str, Any],
    redirect_uri: str,
    user_id: int | None,
) -> OAuthStartResult:
    client_id = str(auth_config.get("client_id") or "").strip()
    client_secret = str(auth_config.get("client_secret") or "").strip()
    if not client_id:
        return OAuthStartResult(
            ok=False,
            error="OAuth client_id is required.",
            hint="Set a client_id in the MCP adapter OAuth settings.",
        )

    authorization_endpoint, token_endpoint, discovery_hint = _discover_oauth_endpoints(mcp_url, auth_config)
    if not authorization_endpoint or not token_endpoint:
        return OAuthStartResult(ok=False, error="OAuth endpoint discovery failed.", hint=discovery_hint)

    state = secrets.token_urlsafe(24)
    code_verifier = _b64url(secrets.token_bytes(48))
    code_challenge = _b64url(hashlib.sha256(code_verifier.encode("utf-8")).digest())

    scopes = _normalize_scopes(auth_config.get("scopes"))
    resource = str(auth_config.get("resource") or mcp_url or "").strip()
    audience = str(auth_config.get("audience") or "").strip()

    params: dict[str, str] = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if scopes:
        params["scope"] = " ".join(scopes)
    if resource:
        params["resource"] = resource
    if audience:
        params["audience"] = audience

    authorization_params = auth_config.get("authorization_params")
    if isinstance(authorization_params, dict):
        for key, value in authorization_params.items():
            key_str = str(key or "").strip()
            if not key_str:
                continue
            value_str = str(value or "").strip()
            if value_str:
                params[key_str] = value_str

    authorization_url = f"{authorization_endpoint}?{urlencode(params)}"

    flow = {
        "adapter_id": int(adapter_id),
        "user_id": int(user_id) if isinstance(user_id, int) else None,
        "created_at": int(time.time()),
        "status": "pending",
        "error": "",
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
        "client_id": client_id,
        "client_secret": client_secret,
        "token_endpoint": token_endpoint,
        "authorization_endpoint": authorization_endpoint,
        "resource": resource,
        "audience": audience,
        "token_params": auth_config.get("token_params") if isinstance(auth_config.get("token_params"), dict) else {},
        "has_access_token": False,
    }

    cache.set(_cache_key(state), flow, timeout=PENDING_TTL_SECONDS)
    return OAuthStartResult(
        ok=True,
        authorization_url=authorization_url,
        state=state,
        expires_in=PENDING_TTL_SECONDS,
    )


def get_oauth_flow_status(
    *,
    state: str,
    adapter_id: int,
    user_id: int | None,
) -> OAuthStatusResult:
    payload = cache.get(_cache_key(state))
    if not isinstance(payload, dict):
        return OAuthStatusResult(ok=False, status="expired", error="OAuth session not found or expired.")

    if int(payload.get("adapter_id") or -1) != int(adapter_id):
        return OAuthStatusResult(ok=False, status="error", error="OAuth session does not match this adapter.")

    expected_user_id = payload.get("user_id")
    if isinstance(expected_user_id, int) and isinstance(user_id, int) and expected_user_id != user_id:
        return OAuthStatusResult(ok=False, status="error", error="OAuth session belongs to a different user.")

    status_value = str(payload.get("status") or "pending")
    return OAuthStatusResult(
        ok=True,
        status=status_value,
        error=str(payload.get("error") or ""),
        has_access_token=bool(payload.get("has_access_token")),
    )


def _token_exchange(
    *,
    token_endpoint: str,
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
    code_verifier: str,
    resource: str,
    audience: str,
    extra_token_params: dict[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    payload: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }
    if client_secret:
        payload["client_secret"] = client_secret
    if resource:
        payload["resource"] = resource
    if audience:
        payload["audience"] = audience
    for key, value in (extra_token_params or {}).items():
        key_str = str(key or "").strip()
        val_str = str(value or "").strip()
        if key_str and val_str:
            payload[key_str] = val_str

    request = Request(
        token_endpoint,
        data=urlencode(payload).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "FixItFelix-OAuth/1.0",
        },
    )

    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return None, body or str(exc.reason or f"HTTP {exc.code}")
    except (URLError, TimeoutError, ValueError) as exc:
        return None, str(getattr(exc, "reason", "") or exc)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None, raw or "Token endpoint returned non-JSON response."

    return parsed if isinstance(parsed, dict) else None, ""


def complete_oauth_flow(
    *,
    state: str,
    code: str,
    error: str,
    error_description: str,
) -> OAuthCompleteResult:
    payload = cache.get(_cache_key(state))
    if not isinstance(payload, dict):
        return OAuthCompleteResult(ok=False, error="OAuth session not found or expired.")

    adapter_id = _to_int(payload.get("adapter_id"))
    if not adapter_id:
        return OAuthCompleteResult(ok=False, error="OAuth session is invalid.")

    if error:
        message = error_description.strip() or error.strip() or "Authorization was denied."
        payload["status"] = "error"
        payload["error"] = message
        cache.set(_cache_key(state), payload, timeout=FINAL_TTL_SECONDS)
        return OAuthCompleteResult(ok=False, adapter_id=adapter_id, error=message)

    if not code:
        message = "Missing authorization code in callback."
        payload["status"] = "error"
        payload["error"] = message
        cache.set(_cache_key(state), payload, timeout=FINAL_TTL_SECONDS)
        return OAuthCompleteResult(ok=False, adapter_id=adapter_id, error=message)

    token_response, exchange_error = _token_exchange(
        token_endpoint=str(payload.get("token_endpoint") or ""),
        code=code,
        redirect_uri=str(payload.get("redirect_uri") or ""),
        client_id=str(payload.get("client_id") or ""),
        client_secret=str(payload.get("client_secret") or ""),
        code_verifier=str(payload.get("code_verifier") or ""),
        resource=str(payload.get("resource") or ""),
        audience=str(payload.get("audience") or ""),
        extra_token_params=payload.get("token_params") if isinstance(payload.get("token_params"), dict) else {},
    )
    if not token_response:
        message = exchange_error or "OAuth token exchange failed."
        payload["status"] = "error"
        payload["error"] = message
        cache.set(_cache_key(state), payload, timeout=FINAL_TTL_SECONDS)
        return OAuthCompleteResult(ok=False, adapter_id=adapter_id, error=message)

    access_token = str(token_response.get("access_token") or "").strip()
    if not access_token:
        message = "Token response did not include an access_token."
        payload["status"] = "error"
        payload["error"] = message
        cache.set(_cache_key(state), payload, timeout=FINAL_TTL_SECONDS)
        return OAuthCompleteResult(ok=False, adapter_id=adapter_id, error=message)

    refresh_token = str(token_response.get("refresh_token") or "").strip()
    token_type = str(token_response.get("token_type") or "").strip()
    scope = str(token_response.get("scope") or "").strip()
    expires_in = _to_int(token_response.get("expires_in"))

    payload["status"] = "success"
    payload["error"] = ""
    payload["has_access_token"] = True
    cache.set(_cache_key(state), payload, timeout=FINAL_TTL_SECONDS)

    return OAuthCompleteResult(
        ok=True,
        adapter_id=adapter_id,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type=token_type,
        expires_in=expires_in,
        scope=scope,
        authorization_endpoint=str(payload.get("authorization_endpoint") or ""),
        token_endpoint=str(payload.get("token_endpoint") or ""),
    )

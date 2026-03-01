import asyncio
from dataclasses import dataclass
from typing import Any

from fastmcp import Client
from fastmcp.client.auth.oauth import OAuth


class OAuthAuthorizationRequired(RuntimeError):
    def __init__(self, authorization_url: str):
        super().__init__("OAuth authorization required")
        self.authorization_url = authorization_url


class CaptureOAuth(OAuth):
    async def redirect_handler(self, authorization_url: str) -> None:
        raise OAuthAuthorizationRequired(authorization_url)

    async def callback_handler(self):
        raise RuntimeError("OAuth callback is not captured by this API flow.")


@dataclass
class OAuthStartResult:
    ok: bool
    authorization_url: str = ""
    error: str = ""
    hint: str = ""


def _normalize_scopes(scopes: Any):
    if isinstance(scopes, list):
        parsed = [str(item).strip() for item in scopes if str(item).strip()]
        return parsed if parsed else None
    if isinstance(scopes, str):
        parsed = [part.strip() for part in scopes.replace(",", " ").split() if part.strip()]
        return parsed if parsed else None
    return None


def start_fastmcp_oauth(
    *,
    mcp_url: str,
    client_id: str | None = None,
    client_secret: str | None = None,
    scopes: Any = None,
    callback_port: int | None = None,
) -> OAuthStartResult:
    async def _run():
        oauth = CaptureOAuth(
            mcp_url=mcp_url,
            scopes=_normalize_scopes(scopes),
            client_name="Fix it Felix MCP OAuth",
            callback_port=callback_port,
            client_id=client_id or None,
            client_secret=client_secret or None,
        )

        async with Client(mcp_url, auth=oauth, timeout=15, init_timeout=15) as client:
            await client.list_tools()

    try:
        asyncio.run(_run())
    except OAuthAuthorizationRequired as exc:
        return OAuthStartResult(ok=True, authorization_url=exc.authorization_url)
    except RuntimeError as exc:
        message = str(exc)
        if "Registration failed: 404" in message:
            return OAuthStartResult(
                ok=False,
                error=message,
                hint=(
                    "OAuth dynamic client registration is unavailable for this MCP provider. "
                    "Set OAuth client_id/client_secret in adapter settings."
                ),
            )
        return OAuthStartResult(ok=False, error=message)
    except Exception as exc:  # pragma: no cover
        return OAuthStartResult(ok=False, error=str(exc))

    return OAuthStartResult(
        ok=False,
        error="OAuth flow did not produce an authorization URL.",
        hint="Verify MCP OAuth configuration and try again.",
    )

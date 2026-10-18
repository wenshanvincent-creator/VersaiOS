"""Authenticated, loopback-only Streamable HTTP transport for phone-use."""

import os
from pathlib import Path
import secrets

import uvicorn

from phone_mcp import mcp


mcp.settings.stateless_http = True
mcp.settings.json_response = True
upstream = mcp.streamable_http_app()
token = Path(os.environ["PHONE_MCP_TOKEN_FILE"]).read_text("utf-8").strip()
if not token:
    raise RuntimeError("Phone MCP access token is empty")


async def app(scope, receive, send):
    if scope["type"] == "http":
        headers = dict(scope["headers"])
        if not secrets.compare_digest(headers.get(b"authorization", b""), ("Bearer " + token).encode()):
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"www-authenticate", b"Bearer")]})
            await send({"type": "http.response.body", "body": b"Unauthorized"})
            return
    await upstream(scope, receive, send)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8766, access_log=False, log_level="warning")

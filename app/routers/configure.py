"""Configure endpoint — shows provider credential status and setup instructions."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.utils.credentials import load_credentials
from app.config.provider_config import PROVIDER_REGISTRY

router = APIRouter()

_PROVIDER_ENV_VARS = {
    "francetv": [],                         # no login required
    "mytf1":    ["MYTF1_LOGIN", "MYTF1_PASSWORD"],
    "6play":    ["SIXPLAY_LOGIN", "SIXPLAY_PASSWORD"],
    "cbc":      ["CBC_LOGIN", "CBC_PASSWORD"],
}

_PROVIDER_NOTES = {
    "francetv": "No credentials required — public content.",
    "mytf1":    "Requires a free TF1+ account (tf1.fr).",
    "6play":    "Requires a free 6play account (6play.fr).",
    "cbc":      "Requires a free CBC Gem account (gem.cbc.ca).",
}


def _get_provider_status() -> dict:
    """Return a dict of provider_key → configuration details."""
    try:
        creds = load_credentials()
    except Exception:
        creds = {}

    status = {}
    for key, config in PROVIDER_REGISTRY.items():
        provider_creds = creds.get(key, {}) if isinstance(creds, dict) else {}
        has_login = bool(provider_creds.get("login") or provider_creds.get("email"))
        has_password = bool(provider_creds.get("password"))
        requires_auth = bool(_PROVIDER_ENV_VARS.get(key))
        if not requires_auth:
            configured = True
            label = "✅ Ready (no auth needed)"
        elif has_login and has_password:
            configured = True
            label = "✅ Credentials configured"
        elif has_login:
            configured = False
            label = "⚠️ Password missing"
        else:
            configured = False
            label = "❌ Not configured"

        status[key] = {
            "display_name": config["display_name"],
            "configured": configured,
            "label": label,
            "note": _PROVIDER_NOTES.get(key, ""),
            "env_vars": _PROVIDER_ENV_VARS.get(key, []),
        }
    return status


@router.get("/configure", response_class=HTMLResponse)
async def configure():
    """Render the addon configuration page."""
    provider_status = _get_provider_status()
    all_ok = all(p["configured"] for p in provider_status.values())

    rows = ""
    for key, info in provider_status.items():
        env_html = ""
        if info["env_vars"]:
            env_html = "<br><small><code>" + "</code>, <code>".join(info["env_vars"]) + "</code></small>"
        rows += f"""
        <tr>
          <td><strong>{info['display_name']}</strong></td>
          <td>{info['label']}</td>
          <td>{info['note']}{env_html}</td>
        </tr>"""

    overall = (
        '<span style="color:#22c55e">✅ All providers ready</span>'
        if all_ok else
        '<span style="color:#f59e0b">⚠️ Some providers need credentials</span>'
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Catch-up TV &amp; More — Configuration</title>
  <style>
    body {{font-family: system-ui, sans-serif; max-width: 860px; margin: 40px auto;
           padding: 0 20px; background: #0f172a; color: #e2e8f0;}}
    h1   {{color: #f8fafc; margin-bottom: 4px;}}
    p    {{color: #94a3b8; margin-top: 0;}}
    table {{width: 100%; border-collapse: collapse; margin-top: 24px;}}
    th   {{text-align: left; padding: 10px 14px; background: #1e293b;
           color: #94a3b8; font-size: .85rem; text-transform: uppercase;
           letter-spacing: .05em;}}
    td   {{padding: 12px 14px; border-bottom: 1px solid #1e293b; vertical-align: top;}}
    tr:last-child td {{border-bottom: none;}}
    code {{background: #1e293b; padding: 2px 6px; border-radius: 4px;
           font-size: .85em; color: #7dd3fc;}}
    .badge {{display: inline-block; padding: 4px 10px; border-radius: 999px;
             font-size: .8rem; font-weight: 600;}}
    .ok  {{background: #14532d; color: #86efac;}}
    .warn{{background: #451a03; color: #fcd34d;}}
    details {{margin-top: 28px;}}
    summary {{cursor: pointer; color: #7dd3fc; font-weight: 600;}}
    pre  {{background: #1e293b; padding: 16px; border-radius: 8px;
           overflow-x: auto; font-size: .85rem; color: #e2e8f0;}}
  </style>
</head>
<body>
  <h1>Catch-up TV &amp; More</h1>
  <p>Stremio addon — provider configuration status</p>

  <p>Overall: {overall}</p>

  <table>
    <thead>
      <tr><th>Provider</th><th>Status</th><th>Notes &amp; env vars</th></tr>
    </thead>
    <tbody>{rows}
    </tbody>
  </table>

  <details>
    <summary>How to configure credentials</summary>
    <p>
      Set credentials via environment variables <em>or</em> in
      <code>credentials.json</code> at the project root.
    </p>
    <p><strong>Environment variables (recommended for deployments):</strong></p>
    <pre>CREDENTIALS_JSON='{{"mytf1":{{"login":"user@example.com","password":"secret"}},
  "6play":{{"login":"user@example.com","password":"secret"}},
  "cbcgem":{{"login":"user@example.com","password":"secret"}}}}'</pre>
    <p><strong>Or in <code>credentials.json</code>:</strong></p>
    <pre>{{
  "mytf1":  {{"login": "user@example.com", "password": "secret"}},
  "6play":  {{"login": "user@example.com", "password": "secret"}},
  "cbcgem": {{"login": "user@example.com", "password": "secret"}}
}}</pre>
  </details>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/configure/status")
async def configure_status():
    """Return provider configuration status as JSON (for programmatic checks)."""
    status = _get_provider_status()
    return {
        "all_configured": all(p["configured"] for p in status.values()),
        "providers": {k: {"configured": v["configured"], "label": v["label"]}
                      for k, v in status.items()},
    }

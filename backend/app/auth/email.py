"""Transactional email (verification + password reset) via Resend.

If no Resend key is configured, it falls back to "dev mode": the link is logged to
the server console and returned by the calling endpoint (in development only), so the
flows are fully testable before Resend is wired. Uses urllib — no extra dependency.
"""

from __future__ import annotations

import json
import urllib.request

from ..core.config import settings
from .security import create_purpose_token

_RESEND_URL = "https://api.resend.com/emails"


def send_email(to: str, subject: str, html: str) -> bool:
    """Send one email. Returns True if Resend accepted it, else False (dev fallback)."""
    if not settings.resend_api_key:
        print(f"[email:dev] would send to {to} | {subject!r} (Resend not configured)")
        return False
    try:
        req = urllib.request.Request(
            _RESEND_URL,
            data=json.dumps({"from": settings.email_from, "to": [to], "subject": subject, "html": html}).encode(),
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                # A real User-Agent — the default urllib one trips Cloudflare (error 1010).
                "User-Agent": "RiskWise/1.0 (+https://riskwise.app)",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception as e:  # never let an email hiccup break signup/reset
        print(f"[email] send to {to} failed: {e}")
        return False


def _shell(title: str, body_html: str, button_text: str, link: str) -> str:
    return f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;background:#0a0a0b;padding:32px;color:#d3d3d6">
      <div style="max-width:480px;margin:0 auto;background:#141416;border:1px solid #2a2a2e;border-radius:16px;padding:28px">
        <div style="font-family:Sora,Arial;font-weight:700;font-size:20px;letter-spacing:1px">
          <span style="color:#f4f1e6">RISK</span><span style="color:#e6c86e">WISE</span>
        </div>
        <h1 style="color:#f4f1e6;font-size:20px;margin:20px 0 8px">{title}</h1>
        <p style="color:#c7d5e6;font-size:14px;line-height:1.6">{body_html}</p>
        <a href="{link}" style="display:inline-block;margin:18px 0;background:#e6c86e;color:#0a0a0a;
           text-decoration:none;font-weight:600;padding:11px 22px;border-radius:10px;font-size:14px">{button_text}</a>
        <p style="color:#6b8099;font-size:12px;line-height:1.6;margin-top:16px">
          If the button doesn't work, paste this link into your browser:<br>
          <span style="color:#93a6bd;word-break:break-all">{link}</span>
        </p>
        <p style="color:#6b8099;font-size:11px;margin-top:20px">
          If you didn't request this, you can safely ignore this email.
        </p>
      </div>
    </div>"""


def send_verification(user) -> str:
    """Email a 24h verification link. Returns the link (for the dev fallback)."""
    token = create_purpose_token(user.id, "verify", 60 * 24)
    link = f"{settings.app_base_url}/?verify={token}"
    send_email(
        user.email,
        "Verify your RiskWise email",
        _shell(
            "Confirm your email",
            f"Hi {user.username}, please confirm this is your email so we know it's really you.",
            "Verify email",
            link,
        ),
    )
    return link


def send_password_reset(user) -> str:
    """Email a 30-minute password-reset link. Returns the link (for the dev fallback)."""
    token = create_purpose_token(user.id, "reset", 30)
    link = f"{settings.app_base_url}/?reset={token}"
    send_email(
        user.email,
        "Reset your RiskWise password",
        _shell(
            "Reset your password",
            f"Hi {user.username}, we got a request to reset your password. This link expires in 30 minutes.",
            "Reset password",
            link,
        ),
    )
    return link

"""HMAC-SHA256 signature verification for X webhook payloads.

X signs every POST payload with your consumer secret and sends the
signature in the x-twitter-webhooks-signature header as "sha256=<base64>".

Reference:
  https://developer.x.com/en/docs/x-api/webhooks
"""

from __future__ import annotations

import base64
import hashlib
import hmac

# Official header name (V2 Webhooks API)
SIGNATURE_HEADER = "x-twitter-webhooks-signature"

# Legacy alias — kept for backward compatibility with older integrations
SIGNATURE_HEADER_LEGACY = "X-Signature-256"


def generate_signature(payload: bytes, consumer_secret: str) -> str:
    """Generate the x-twitter-webhooks-signature header value for a payload.

    Args:
        payload: Raw request body bytes.
        consumer_secret: Your app's consumer secret.

    Returns:
        Header value string, e.g. "sha256=abc123..."
    """
    digest = hmac.new(
        consumer_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).digest()
    return "sha256=" + base64.b64encode(digest).decode("utf-8")


def verify_signature(
    payload: bytes, signature_header: str, consumer_secret: str
) -> bool:
    """Verify a webhook payload against its x-twitter-webhooks-signature header.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        payload: Raw request body bytes.
        signature_header: Value of the x-twitter-webhooks-signature header
                          (or legacy X-Signature-256).
        consumer_secret: Your app's consumer secret.

    Returns:
        True if signature is valid, False otherwise.
    """
    expected = generate_signature(payload, consumer_secret)
    return hmac.compare_digest(expected, signature_header)


def explain_signature(payload: bytes, consumer_secret: str) -> dict:
    """Step-by-step breakdown of signature computation (for debugging).

    Returns a dict with each intermediate value so you can see exactly
    what X is computing and compare it to what you computed.
    """
    key = consumer_secret.encode("utf-8")
    digest = hmac.new(key, payload, hashlib.sha256).digest()
    b64 = base64.b64encode(digest).decode("utf-8")

    return {
        "algorithm": "HMAC-SHA256",
        "key": f"{consumer_secret[:4]}...{consumer_secret[-4:]} ({len(consumer_secret)} chars)",
        "payload_length": len(payload),
        "payload_preview": payload[:64].decode("utf-8", errors="replace")
        + ("..." if len(payload) > 64 else ""),
        "raw_digest_hex": digest.hex(),
        "base64_digest": b64,
        "header_value": f"sha256={b64}",
        "header_name": SIGNATURE_HEADER,
        "header_name_legacy": SIGNATURE_HEADER_LEGACY,
    }

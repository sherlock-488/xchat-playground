"""CRC challenge response for X webhook registration.

X sends a GET request with ?crc_token=<token> to verify your endpoint.
You must respond with the HMAC-SHA256 of the token, signed with your
consumer secret, base64-encoded, prefixed with "sha256=".

Reference:
  https://developer.x.com/en/docs/x-api/webhooks
"""

from __future__ import annotations

import base64
import hashlib
import hmac


def compute_crc_response(crc_token: str, consumer_secret: str) -> dict:
    """Compute the CRC challenge response dict.

    Args:
        crc_token: The token sent by X in the ?crc_token= query param.
        consumer_secret: Your app's consumer secret (OAuth 1.0a).

    Returns:
        Dict with 'response_token' key, ready to return as JSON body.
    """
    digest = hmac.new(
        consumer_secret.encode("utf-8"),
        crc_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    response_token = "sha256=" + base64.b64encode(digest).decode("utf-8")
    return {"response_token": response_token}


def verify_crc_token(crc_token: str, consumer_secret: str, expected: str) -> bool:
    """Verify that a CRC response matches the expected value.

    Useful for testing your CRC handler end-to-end.
    """
    computed = compute_crc_response(crc_token, consumer_secret)
    return hmac.compare_digest(computed["response_token"], expected)

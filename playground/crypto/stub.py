"""Stub crypto mode — no real keys needed.

In stub mode, "encrypted" payloads are just base64-encoded plaintext
prefixed with STUB_ENC_. This lets you walk through the full
decrypt → handle → reply flow without any X credentials.

This is the default mode for xchat-playground.
"""

from __future__ import annotations

import base64

STUB_PREFIX = "STUB_ENC_"


class StubCrypto:
    """Stub decryption for testing without real XChat key material.

    The simulator encodes plaintext as:
        STUB_ENC_<base64(plaintext)>

    StubCrypto reverses this, giving you the original plaintext.
    For any other payload format, it returns a descriptive placeholder.
    """

    def decrypt(self, encrypted_content: str) -> dict:
        """Decrypt a stub-encrypted payload.

        Args:
            encrypted_content: Value from message.encrypted_content field.

        Returns:
            Dict with 'plaintext', 'mode', and 'notes' keys.
        """
        if encrypted_content.startswith(STUB_PREFIX):
            b64 = encrypted_content[len(STUB_PREFIX):]
            try:
                plaintext = base64.b64decode(b64).decode("utf-8")
                return {
                    "plaintext": plaintext,
                    "mode": "stub",
                    "notes": "Decoded from STUB_ENC_ prefix. No real keys used.",
                }
            except Exception as e:
                return {
                    "plaintext": None,
                    "mode": "stub",
                    "notes": f"Failed to decode stub payload: {e}",
                }
        else:
            return {
                "plaintext": f"[REAL_ENCRYPTED: {encrypted_content[:40]}...]",
                "mode": "stub",
                "notes": (
                    "This looks like a real encrypted payload. "
                    "Use 'playground crypto real' with state.json for real decryption."
                ),
            }

    def encrypt(self, plaintext: str) -> str:
        """Encode plaintext as a stub-encrypted payload."""
        b64 = base64.b64encode(plaintext.encode("utf-8")).decode("utf-8")
        return f"{STUB_PREFIX}{b64}"

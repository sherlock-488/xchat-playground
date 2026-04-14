"""Real-key crypto mode — decrypt XChat messages using state.json.

Requires a state.json produced by xchat-bot-python's login + unlock flow:
  uv run python main.py login
  uv run python main.py unlock

state.json contains:
  {
    "private_keys": { ... },
    "signing_key_version": "...",
    "user_id": "..."
  }

XChat uses XChaCha20-Poly1305 for message encryption.
Each message includes a per-recipient encrypted key blob.

IMPORTANT:
  - Never commit state.json to git (it contains your private keys)
  - This module requires the 'cryptography' package (included in dependencies)
  - If xchat-bot-python's chat-xdk updates its key format, this module
    may need updating. Check the xchat-bot-python changelog.

Reference:
  https://github.com/xdevplatform/xchat-bot-python
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any


class RealCrypto:
    """Decrypt XChat messages using private keys from state.json.

    This is a best-effort implementation based on the xchat-bot-python
    template. The exact key derivation and encryption format may change
    as chat-xdk reaches its official release.

    For production bots, use the official xchat-bot-python decrypt
    utilities directly rather than this module.
    """

    def __init__(self, state_file: Path = Path("state.json")):
        self.state_file = state_file
        self._state: dict[str, Any] = {}
        self._load_state()

    def _load_state(self) -> None:
        if not self.state_file.exists():
            raise FileNotFoundError(
                f"state.json not found at {self.state_file}. "
                "Run xchat-bot-python login + unlock first."
            )
        self._state = json.loads(self.state_file.read_text())

    def decrypt(self, encrypted_content: str, recipient_key_blob: str | None = None) -> dict:
        """Attempt to decrypt a real XChat message payload.

        Args:
            encrypted_content: The encrypted_content field from the event.
            recipient_key_blob: The per-recipient key blob (from recipient_keys[user_id]).

        Returns:
            Dict with 'plaintext', 'mode', 'key_id', and 'notes'.
        """
        # Validate we have key material
        private_keys = self._state.get("private_keys", {})
        user_id = self._state.get("user_id", "unknown")
        key_version = self._state.get("signing_key_version", "unknown")

        if not private_keys:
            return {
                "plaintext": None,
                "mode": "real",
                "key_id": None,
                "notes": "No private_keys found in state.json. Re-run unlock.",
            }

        # Stub implementation note:
        # The actual XChaCha20-Poly1305 decrypt requires:
        #   1. Decrypt the per-recipient key blob using your private key (X25519 ECDH)
        #   2. Use the decrypted symmetric key to decrypt the message body
        #
        # The exact format is defined in xchat-bot-python/chat-xdk (not yet released).
        # This placeholder shows the expected flow and will be updated when chat-xdk
        # publishes its stable API.

        try:
            # Attempt basic base64 decode to check if it's a stub payload
            from playground.crypto.stub import StubCrypto, STUB_PREFIX
            if encrypted_content.startswith(STUB_PREFIX):
                stub_result = StubCrypto().decrypt(encrypted_content)
                stub_result["mode"] = "real-fallback-stub"
                stub_result["key_id"] = key_version
                stub_result["notes"] = "Stub payload detected in real-key mode. Using stub decode."
                return stub_result

            # Real encrypted payload — attempt XChaCha20-Poly1305 decrypt
            return self._xchacha20_decrypt(encrypted_content, recipient_key_blob, private_keys)

        except Exception as e:
            return {
                "plaintext": None,
                "mode": "real",
                "key_id": key_version,
                "notes": f"Decryption failed: {e}. Check chat-xdk docs for current format.",
            }

    def _xchacha20_decrypt(
        self,
        encrypted_content: str,
        recipient_key_blob: str | None,
        private_keys: dict,
    ) -> dict:
        """XChaCha20-Poly1305 decrypt flow (chat-xdk format).

        This is a placeholder that documents the expected algorithm.
        Full implementation requires chat-xdk's stable release.
        """
        # Step 1: Get your private key (most recent version)
        key_version = max(private_keys.keys()) if private_keys else None
        private_key_b64 = private_keys.get(key_version) if key_version else None

        if not private_key_b64:
            raise ValueError("No private key found for decryption")

        # Step 2: Decode the encrypted content
        try:
            encrypted_bytes = base64.b64decode(encrypted_content)
        except Exception:
            raise ValueError(f"Cannot base64-decode encrypted_content: {encrypted_content[:40]}...")

        # Step 3: Placeholder — real implementation needs chat-xdk
        # When chat-xdk is released, replace this with:
        #   from chat_xdk import decrypt_message
        #   plaintext = decrypt_message(private_key_b64, recipient_key_blob, encrypted_bytes)
        return {
            "plaintext": None,
            "mode": "real",
            "key_id": key_version,
            "notes": (
                "chat-xdk not yet officially released. "
                "This module will be updated when xdevplatform/xchat-bot-python "
                "publishes the stable chat-xdk API. "
                f"Encrypted payload length: {len(encrypted_bytes)} bytes. "
                f"Private key version: {key_version}."
            ),
        }

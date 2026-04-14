"""Tests for the crypto module (stub and real modes)."""

from playground.crypto.stub import STUB_PREFIX, StubCrypto


class TestStubCrypto:
    def test_encrypt_produces_stub_prefix(self):
        crypto = StubCrypto()
        result = crypto.encrypt("hello")
        assert result.startswith(STUB_PREFIX)

    def test_decrypt_stub_payload(self):
        crypto = StubCrypto()
        encrypted = crypto.encrypt("Hello, XChat!")
        result = crypto.decrypt(encrypted)
        assert result["plaintext"] == "Hello, XChat!"
        assert result["mode"] == "stub"

    def test_decrypt_roundtrip(self):
        crypto = StubCrypto()
        for text in ["hello", "世界", "emoji 🎉", "special !@#$%"]:
            encrypted = crypto.encrypt(text)
            result = crypto.decrypt(encrypted)
            assert result["plaintext"] == text

    def test_decrypt_real_payload_returns_placeholder(self):
        crypto = StubCrypto()
        result = crypto.decrypt("REAL_ENCRYPTED_PAYLOAD_XYZ")
        assert result["plaintext"].startswith("[REAL_ENCRYPTED:")
        assert result["mode"] == "stub"
        assert (
            "real-key" in result["notes"].lower() or "real" in result["notes"].lower()
        )

    def test_decrypt_invalid_stub_graceful(self):
        crypto = StubCrypto()
        # Invalid base64 after prefix
        result = crypto.decrypt(f"{STUB_PREFIX}!!!not_valid_base64!!!")
        assert result["plaintext"] is None
        assert "Failed" in result["notes"]

    def test_decrypt_empty_payload(self):
        crypto = StubCrypto()
        result = crypto.decrypt("")
        # Empty string doesn't start with STUB_PREFIX → real payload path
        assert result["mode"] == "stub"

    def test_encrypt_decrypt_unicode(self):
        crypto = StubCrypto()
        text = "XChat 🚀 テスト"
        assert crypto.decrypt(crypto.encrypt(text))["plaintext"] == text

    def test_stub_fixture_payload(self):
        """Test the exact payload format used in bundled fixtures."""
        crypto = StubCrypto()
        fixture_payload = "STUB_ENC_SGVsbG8gZnJvbSB4Y2hhdC1wbGF5Z3JvdW5kIQ=="
        result = crypto.decrypt(fixture_payload)
        assert result["plaintext"] == "Hello from xchat-playground!"

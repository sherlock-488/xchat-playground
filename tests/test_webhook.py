"""Tests for webhook CRC and signature modules."""

from playground.webhook.crc import compute_crc_response, verify_crc_token
from playground.webhook.signature import (
    explain_signature,
    generate_signature,
    verify_signature,
)

SECRET = "test_consumer_secret_abc123"
WRONG_SECRET = "wrong_secret_xyz"


class TestCRC:
    def test_compute_crc_response_returns_dict(self):
        result = compute_crc_response("some_token", SECRET)
        assert isinstance(result, dict)
        assert "response_token" in result

    def test_crc_response_starts_with_sha256(self):
        result = compute_crc_response("some_token", SECRET)
        assert result["response_token"].startswith("sha256=")

    def test_crc_is_deterministic(self):
        r1 = compute_crc_response("token123", SECRET)
        r2 = compute_crc_response("token123", SECRET)
        assert r1["response_token"] == r2["response_token"]

    def test_different_tokens_produce_different_responses(self):
        r1 = compute_crc_response("token_a", SECRET)
        r2 = compute_crc_response("token_b", SECRET)
        assert r1["response_token"] != r2["response_token"]

    def test_different_secrets_produce_different_responses(self):
        r1 = compute_crc_response("token", SECRET)
        r2 = compute_crc_response("token", WRONG_SECRET)
        assert r1["response_token"] != r2["response_token"]

    def test_verify_crc_token_valid(self):
        token = "test_crc_token"
        expected = compute_crc_response(token, SECRET)["response_token"]
        assert verify_crc_token(token, SECRET, expected) is True

    def test_verify_crc_token_invalid(self):
        token = "test_crc_token"
        assert verify_crc_token(token, SECRET, "sha256=wrongvalue") is False


class TestSignature:
    def test_generate_signature_format(self):
        sig = generate_signature(b"payload", SECRET)
        assert sig.startswith("sha256=")

    def test_verify_signature_valid(self):
        payload = b'{"event_type":"chat.received"}'
        sig = generate_signature(payload, SECRET)
        assert verify_signature(payload, sig, SECRET) is True

    def test_verify_signature_wrong_secret(self):
        payload = b'{"event_type":"chat.received"}'
        sig = generate_signature(payload, SECRET)
        assert verify_signature(payload, sig, WRONG_SECRET) is False

    def test_verify_signature_tampered_payload(self):
        payload = b'{"event_type":"chat.received"}'
        tampered = b'{"event_type":"chat.received","extra":"injected"}'
        sig = generate_signature(payload, SECRET)
        assert verify_signature(tampered, sig, SECRET) is False

    def test_verify_signature_empty_payload(self):
        sig = generate_signature(b"", SECRET)
        assert verify_signature(b"", sig, SECRET) is True

    def test_explain_signature_keys(self):
        result = explain_signature(b"test payload", SECRET)
        assert "algorithm" in result
        assert "header_value" in result
        assert "raw_digest_hex" in result
        assert "base64_digest" in result
        assert result["algorithm"] == "HMAC-SHA256"
        assert result["header_value"].startswith("sha256=")

    def test_explain_signature_masks_secret(self):
        result = explain_signature(b"test", "supersecret12345")
        # Should not expose full secret
        assert "supersecret12345" not in result["key"]

    def test_signature_is_deterministic(self):
        payload = b"hello world"
        s1 = generate_signature(payload, SECRET)
        s2 = generate_signature(payload, SECRET)
        assert s1 == s2

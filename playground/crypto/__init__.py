"""Crypto sandbox — stub or real-key XChat message decryption."""

from .real import RealCrypto
from .stub import StubCrypto

__all__ = ["StubCrypto", "RealCrypto"]

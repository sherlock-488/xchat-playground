"""Repro pack registry — one-click presets for known XChat API issues."""

from __future__ import annotations

from playground.repro.packs.chat_webhook_not_received import ChatWebhookNotReceivedPack
from playground.repro.packs.encrypted_lookup_empty import EncryptedLookupEmptyPack
from playground.repro.packs.legacy_dm_stops_after_e2ee import LegacyDmStopsAfterE2eePack


class ReproRegistry:
    """Registry of all available repro packs."""

    _packs = {
        "chat-webhook-not-received": ChatWebhookNotReceivedPack,
        "encrypted-lookup-empty": EncryptedLookupEmptyPack,
        "legacy-dm-stops-after-e2ee": LegacyDmStopsAfterE2eePack,
    }

    @classmethod
    def get(cls, pack_id: str):
        klass = cls._packs.get(pack_id)
        if not klass:
            raise ValueError(
                f"Unknown repro pack: '{pack_id}'. Available: {list(cls._packs.keys())}"
            )
        return klass()


def list_packs() -> list[dict]:
    """Return metadata for all available repro packs."""
    result = []
    for pack_id, klass in ReproRegistry._packs.items():
        instance = klass()
        result.append(
            {
                "id": pack_id,
                "title": instance.title,
                "description": instance.description,
                "forum_url": getattr(instance, "forum_url", None),
            }
        )
    return result


def run_pack(pack_id: str, verbose: bool = False) -> dict:
    """Run a repro pack by ID and return results."""
    pack = ReproRegistry.get(pack_id)
    return pack.run(verbose=verbose)


def check_pack(pack_id: str, **kwargs) -> dict:
    """Run the semi-automatic checker for a repro pack (if it has one).

    Returns a checklist dict, or raises AttributeError if the pack has no checker.
    """
    pack = ReproRegistry.get(pack_id)
    if not hasattr(pack, "check"):
        raise AttributeError(f"Pack '{pack_id}' does not implement a check() method.")
    return pack.check(**kwargs)


class BaseReproPack:
    """Base class for all repro packs."""

    title: str = "Untitled"
    description: str = ""
    forum_url: str | None = None

    def run(self, verbose: bool = False) -> dict:
        raise NotImplementedError

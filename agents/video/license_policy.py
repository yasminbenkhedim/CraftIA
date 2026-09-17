"""
LicensePolicyEvaluator -- Central License & Attribution Evaluator for VideoAgent.

Default-DENY. An asset is usable only if its licence matches a known-commercial-safe
identifier on the allowlist below. Anything unrecognised, empty, ambiguous, or carrying
a NonCommercial / NoDerivatives / ShareAlike term is rejected.

Why this was rewritten (LICENSES.md R5)
---------------------------------------
The previous implementation was default-ALLOW and had a substring bug that made it
accept exactly the licences it existed to block:

    if "cc-by" in lic_str or "by" in lic_str or "attribution" in lic_str:

`"by" in "cc-by-nc-4.0"` is True, and that branch was evaluated *before* the
non-commercial rejection further down -- so the rejection was unreachable for every
`by-nc*` and `by-nd*` variant. Verified against the real evaluator: cc-by-nc-4.0,
CC BY-NC-SA 4.0, by-nc-nd and cc-by-nd-4.0 were all ACCEPTED as plain CC-BY, and an
empty licence string was accepted as CC0. Two further default-allow paths granted
unknown Openverse licences "benefit of CC0", and accepted any unrecognised string as
CC0 at 0.80 confidence.

Design rules now
----------------
1. Allowlist, not blocklist. Unknown means rejected, always.
2. Restriction terms are matched on token boundaries (`nc`, `nd`, `sa` as whole tokens),
   never as substrings -- so "Sanders" does not trip the ShareAlike check and
   "cc-by-nc" does not slip past as plain attribution.
3. Restriction check runs FIRST, before any acceptance branch, so no ordering accident
   can make it unreachable again.
4. CC-BY is allowlisted but requires a non-empty attribution string; without one it is
   rejected rather than silently used.
"""
import re
import logging
from enum import Enum
from typing import Tuple, Optional

logger = logging.getLogger("uvicorn")


class LicenseType(str, Enum):
    CC0 = "cc0"
    PDM = "pdm"
    CC_BY = "cc_by"
    PEXELS_FREE = "pexels_free"
    LOCAL_PERMISSIVE = "local_permissive"
    UNKNOWN = "unknown"
    INCOMPATIBLE = "incompatible"


# Providers whose output is permissive by construction (we generated or own it).
_TRUSTED_LOCAL_PROVIDERS = frozenset({
    "local_asset", "procedural_overlay", "procedural_background", "user_upload",
})

# Providers operating under a blanket commercial licence rather than per-asset terms.
_PEXELS_PROVIDERS = frozenset({"pexels_stock", "pexels_video"})

# Exact licence identifiers that are safe for commercial use, normalized (see _normalize).
# Keep this list short and explicit -- every addition is a legal decision, not a tweak.
_ALLOWLIST = {
    "cc0": LicenseType.CC0,
    "cc0 1.0": LicenseType.CC0,
    "cc-zero": LicenseType.CC0,
    "zero": LicenseType.CC0,
    "publicdomain": LicenseType.PDM,
    "public domain": LicenseType.PDM,
    "public domain mark": LicenseType.PDM,
    "pdm": LicenseType.PDM,
    "pdm 1.0": LicenseType.PDM,
    "no known copyright": LicenseType.PDM,
    "cc-by": LicenseType.CC_BY,
    "cc-by 4.0": LicenseType.CC_BY,
    "cc-by 3.0": LicenseType.CC_BY,
    "cc-by 2.0": LicenseType.CC_BY,
    "by": LicenseType.CC_BY,
    "pexels": LicenseType.PEXELS_FREE,
    "pexels license": LicenseType.PEXELS_FREE,
}

# Restriction tokens. Matched as whole tokens against the normalized identifier.
#   nc = NonCommercial     -> unusable in a paid product
#   nd = NoDerivatives     -> we composite and edit, which creates a derivative
#   sa = ShareAlike        -> would force our output under the same copyleft terms
_RESTRICTED_TOKENS = frozenset({"nc", "nd", "sa"})

# Phrases that mark a licence as unusable regardless of tokenization.
_RESTRICTED_PHRASES = (
    "noncommercial", "non-commercial", "non commercial",
    "noderiv", "no-deriv", "no deriv",
    "sharealike", "share-alike", "share alike",
    "all rights reserved", "rights reserved", "editorial use only",
    "research only", "research purposes", "personal use only",
)

_SEPARATORS = re.compile(r"[\s_/|,()]+")


def _normalize(license_name: Optional[str]) -> str:
    """
    Lowercases and collapses a raw licence string to a comparable identifier.

    Openverse returns bare codes ('by-nc-sa'); other providers return prose
    ('Creative Commons Attribution 4.0'). Both normalize into hyphen-joined tokens.
    """
    s = (license_name or "").strip().lower()
    if not s:
        return ""
    s = s.replace("creative commons", "cc").replace("attribution", "by")
    s = _SEPARATORS.sub(" ", s).strip()
    s = re.sub(r"\bcc\s+", "cc-", s)          # "cc by" -> "cc-by"
    s = re.sub(r"\bcc-by\s+(?=[a-z])", "cc-by-", s)  # "cc-by nc" -> "cc-by-nc"
    # OpenverseStockProvider builds license_name as f"CC {code.upper()}", so a CC0 asset
    # arrives as "CC CC0" and normalizes to the doubled "cc-cc0". Collapse that: without
    # this, every genuinely public-domain Openverse asset is rejected as unrecognised,
    # which silently empties the only provider that supplies CC0 imagery.
    s = re.sub(r"^cc-(cc0|zero|pdm|publicdomain|public domain)\b", r"\1", s)
    return s.strip()


def _tokens(normalized: str) -> set:
    """Splits a normalized identifier into whole tokens for boundary-safe matching."""
    return {t for t in re.split(r"[-\s]+", normalized) if t}


class LicensePolicyEvaluator:
    """Evaluates media candidate licences and attribution strings. Default-deny."""

    @classmethod
    def evaluate(
        cls,
        license_name: Optional[str],
        attribution: Optional[str],
        provider_id: str,
    ) -> Tuple[bool, LicenseType, float, Optional[str]]:
        """
        Evaluates a candidate licence.
        Returns (is_valid, license_type, license_quality_score, rejection_reason).
        """
        normalized = _normalize(license_name)
        attribution = (attribution or "").strip()
        provider_id = (provider_id or "").strip().lower()

        # 1. Assets we generated or the user supplied. No third-party licence involved.
        if provider_id in _TRUSTED_LOCAL_PROVIDERS:
            return True, LicenseType.LOCAL_PERMISSIVE, 1.0, None

        # 2. Restriction check FIRST, so no later branch can shadow it. This is the
        #    ordering mistake that made the previous implementation fail open.
        blocked = cls._restriction_reason(normalized)
        if blocked:
            return False, LicenseType.INCOMPATIBLE, 0.0, blocked

        # 3. Blanket-licensed providers. Pexels grants commercial use with no attribution
        #    requirement, so a missing per-asset licence string is expected here.
        if provider_id in _PEXELS_PROVIDERS:
            return True, LicenseType.PEXELS_FREE, 1.0, None

        # 4. Empty or unrecognised licence -> rejected. No "benefit of the doubt" path.
        if not normalized:
            return False, LicenseType.UNKNOWN, 0.0, "MISSING_LICENSE"

        lic_type = _ALLOWLIST.get(normalized)
        if lic_type is None:
            lic_type = cls._match_versioned(normalized)
        if lic_type is None:
            logger.info(
                f"LicensePolicyEvaluator: rejecting unrecognised licence "
                f"{license_name!r} (normalized {normalized!r}) from provider {provider_id!r}."
            )
            return False, LicenseType.UNKNOWN, 0.0, "UNRECOGNISED_LICENSE"

        # 5. CC-BY is usable but only with a real attribution string attached.
        if lic_type is LicenseType.CC_BY:
            if len(attribution) < 3:
                return False, LicenseType.CC_BY, 0.0, "MISSING_REQUIRED_ATTRIBUTION"
            return True, LicenseType.CC_BY, 0.85, None

        return True, lic_type, 1.0, None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _restriction_reason(normalized: str) -> Optional[str]:
        """Returns a rejection reason when the licence carries a restriction, else None."""
        if not normalized:
            return None
        for phrase in _RESTRICTED_PHRASES:
            if phrase in normalized:
                return "NON_COMMERCIAL_OR_RESTRICTED_LICENSE"
        if _tokens(normalized) & _RESTRICTED_TOKENS:
            return "NON_COMMERCIAL_OR_RESTRICTED_LICENSE"
        return None

    @staticmethod
    def _match_versioned(normalized: str) -> Optional[LicenseType]:
        """
        Allows a trailing version on an allowlisted base ('cc-by-4.0', 'cc0-1.0').

        Only reached after the restriction check, so a versioned NC variant can never
        arrive here. The base is rebuilt from leading non-numeric tokens, which keeps
        'cc-by-4.0' matching 'cc-by' without also matching 'cc-by-nc'.
        """
        parts = [t for t in re.split(r"[-\s]+", normalized) if t]
        base = []
        for t in parts:
            if re.match(r"^\d", t):
                break
            base.append(t)
        if not base:
            return None
        return _ALLOWLIST.get("-".join(base)) or _ALLOWLIST.get(" ".join(base))

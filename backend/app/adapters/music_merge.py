"""Music title normalization and merge helpers."""

from __future__ import annotations

import re

_FEAT_RE = re.compile(
    r"\s*[\(\[]?\s*(feat\.?|ft\.?|featuring|with)\s+.+?[\)\]]?\s*$",
    re.IGNORECASE,
)
_NOISE_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    """Casefold, strip featuring noise and punctuation for merge keys."""
    text = title.strip()
    text = _FEAT_RE.sub("", text)
    # Drop common edition suffixes in parens for merge key only
    text = re.sub(r"\s*[\(\[].*?(deluxe|remaster|edition|explicit).*?[\)\]]", "", text, flags=re.I)
    text = _NOISE_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text.casefold()


def consensus_genres(genre_lists: list[list[str]], *, limit: int = 8) -> list[str]:
    scores: dict[str, int] = {}
    for genres in genre_lists:
        for g in genres:
            key = g.strip().casefold()
            if not key:
                continue
            scores[key] = scores.get(key, 0) + 1
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    # Prefer original casing from first occurrence
    seen = {k for k, _ in ranked}
    result: list[str] = []
    for genres in genre_lists:
        for g in genres:
            if g.strip().casefold() in seen and g not in result:
                result.append(g)
                if len(result) >= limit:
                    return result
    return result[:limit]

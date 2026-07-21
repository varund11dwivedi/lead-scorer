"""Collapse duplicate leads, keeping the best-scored record of each company."""
from __future__ import annotations

from dataclasses import dataclass, field

from .score import Scored


@dataclass
class DedupeResult:
    kept: list[Scored] = field(default_factory=list)
    merged: dict[str, list[str]] = field(default_factory=dict)

    @property
    def removed(self) -> int:
        return sum(len(v) for v in self.merged.values())


def dedupe(scored: list[Scored]) -> DedupeResult:
    best: dict[str, Scored] = {}
    merged: dict[str, list[str]] = {}
    loose: list[Scored] = []

    for s in scored:
        key = s.lead.company_key
        if not key:
            loose.append(s)            # nothing to match on; never silently drop
            continue
        if key not in best:
            best[key] = s
            merged.setdefault(key, [])
        else:
            keep, drop = ((s, best[key]) if s.score > best[key].score
                          else (best[key], s))
            best[key] = keep
            merged[key].append(drop.lead.email or drop.lead.company or "?")

    return DedupeResult(kept=list(best.values()) + loose,
                        merged={k: v for k, v in merged.items() if v})

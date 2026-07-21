"""Transparent, rule-based lead scoring.

Every point is attributable. When sales asks why a lead scored 72, the answer
is a list of rules and weights - not "the model said so". That auditability is
what gets a scoring system adopted instead of quietly ignored.

Weights are config, not code: tune them against closed-won data.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .normalize import Lead, is_business_email, is_role_email

SENIORITY = {
    "founder": 25, "ceo": 25, "cto": 25, "coo": 22, "cfo": 22, "chief": 22,
    "president": 20, "vp": 20, "vice president": 20, "head of": 18,
    "director": 16, "principal": 14, "lead": 10, "senior": 8,
    "manager": 8, "analyst": 4, "intern": -10, "student": -15,
}
DEFAULT_WEIGHTS = {
    "business_email": 20,
    "role_email_penalty": -10,
    "has_company": 10,
    "size_sweet_spot": 15,      # 50-1000 employees
    "size_enterprise": 8,
    "size_micro_penalty": -5,   # under 5
    "target_country": 10,
    "inbound_source": 12,
}
TARGET_COUNTRIES = {"united states", "us", "usa", "united kingdom", "uk",
                    "canada", "australia", "germany", "netherlands"}
INBOUND = {"demo_request", "contact_form", "pricing_page", "referral", "inbound"}


@dataclass
class Scored:
    lead: Lead
    score: int
    reasons: list[tuple[str, int]] = field(default_factory=list)
    band: str = "cold"

    def explain(self) -> str:
        parts = [f"{n} {v:+d}" for n, v in self.reasons]
        return f"{self.score} ({self.band}): " + ", ".join(parts)


def seniority_points(title: str | None) -> tuple[str, int] | None:
    if not title:
        return None
    t = title.lower()
    best = None
    for word, pts in SENIORITY.items():
        # Word boundaries matter more than they look: a plain `word in t`
        # finds "cto" inside "Director" and scores an engineering director
        # as a C-level. Cost me a wrong ranking before I spotted it.
        if re.search(rf"\b{re.escape(word)}\b", t) and (
                best is None or abs(pts) > abs(best[1])):
            best = (f"title:{word}", pts)
    return best


def band_for(score: int) -> str:
    if score >= 60:
        return "hot"
    if score >= 35:
        return "warm"
    return "cold"


def score_lead(lead: Lead, weights: dict | None = None) -> Scored:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    reasons: list[tuple[str, int]] = []

    if is_business_email(lead.email):
        reasons.append(("business_email", w["business_email"]))
    if is_role_email(lead.email):
        reasons.append(("role_email", w["role_email_penalty"]))
    if lead.company:
        reasons.append(("has_company", w["has_company"]))

    sp = seniority_points(lead.title)
    if sp:
        reasons.append(sp)

    if lead.employees is not None:
        if 50 <= lead.employees <= 1000:
            reasons.append(("size_50_1000", w["size_sweet_spot"]))
        elif lead.employees > 1000:
            reasons.append(("size_enterprise", w["size_enterprise"]))
        elif lead.employees < 5:
            reasons.append(("size_under_5", w["size_micro_penalty"]))

    if lead.country and lead.country.strip().lower() in TARGET_COUNTRIES:
        reasons.append(("target_country", w["target_country"]))
    if lead.source and lead.source.strip().lower() in INBOUND:
        reasons.append(("inbound", w["inbound_source"]))

    total = max(0, min(100, sum(v for _, v in reasons)))
    return Scored(lead=lead, score=total, reasons=reasons, band=band_for(total))

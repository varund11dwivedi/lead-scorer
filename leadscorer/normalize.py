"""Clean lead records before anything scores or dedupes them.

Most 'AI lead scoring' failures are not model failures. They are two rows for
the same company because one says 'Acme, Inc.' and the other says 'ACME Inc',
and a personal gmail address counted as a business domain.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

FREE_EMAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
              "icloud.com", "aol.com", "proton.me", "protonmail.com",
              "gmx.com", "mail.com", "yandex.com"}
ROLE_LOCAL = {"info", "support", "sales", "admin", "contact", "hello",
              "help", "office", "team", "noreply", "no-reply", "billing"}
# Compared token-by-token, not as a suffix string: "inc" should strip from
# "Acme Inc" but must never eat the "co" out of "Vico".
SUFFIXES = {"inc", "llc", "l.l.c.", "ltd", "limited", "corp", "corporation",
            "gmbh", "bv", "b.v.", "plc", "co", "company", "pvt", "private"}
# Deliberately NOT here: "holdings", "group", "partners". They are legal-ish
# but they carry meaning - "Acme Holdings" and "Acme" can be different entities.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)


def normalize_company(name: str | None) -> str | None:
    if not name:
        return None
    s = re.sub(r"[^\w\s.&-]", " ", name.lower())
    tokens = [t for t in re.split(r"\s+", s) if t]
    while tokens and tokens[-1].rstrip(".") in {x.rstrip(".") for x in SUFFIXES}:
        tokens.pop()
    return " ".join(tokens).strip(" .,-") or None


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    e = email.strip().lower()
    return e if EMAIL_RE.match(e) else None


def domain_of(email: str | None) -> str | None:
    e = normalize_email(email)
    return e.split("@", 1)[1] if e else None


def is_business_email(email: str | None) -> bool:
    d = domain_of(email)
    return bool(d) and d not in FREE_EMAIL


def is_role_email(email: str | None) -> bool:
    e = normalize_email(email)
    return bool(e) and e.split("@", 1)[0] in ROLE_LOCAL


@dataclass
class Lead:
    email: str | None = None
    company: str | None = None
    title: str | None = None
    country: str | None = None
    employees: int | None = None
    source: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def domain(self) -> str | None:
        return domain_of(self.email)

    @property
    def company_key(self) -> str | None:
        """What dedupe actually compares - domain beats name when present."""
        return self.domain if is_business_email(self.email) \
            else normalize_company(self.company)


def parse(row: dict) -> Lead:
    def g(*names):
        for n in names:
            for k, v in row.items():
                if k.strip().lower().replace(" ", "_") == n and v not in ("", None):
                    return v
        return None
    emp = g("employees", "employee_count", "size", "headcount")
    try:
        emp = int(str(emp).replace(",", "").split("-")[0]) if emp else None
    except ValueError:
        emp = None
    return Lead(email=normalize_email(g("email", "email_address", "work_email")),
                company=g("company", "company_name", "organization", "account"),
                title=g("title", "job_title", "position", "role"),
                country=g("country", "location", "region"),
                employees=emp, source=g("source", "channel", "utm_source"),
                raw=row)

import pytest

from leadscorer import (Lead, band_for, dedupe, domain_of, is_business_email,
                        is_role_email, normalize_company, normalize_email,
                        parse, score_lead)


# --- normalization ---------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Northwind Logistics, Inc.", "northwind logistics"),
    ("NORTHWIND LOGISTICS LLC", "northwind logistics"),
    ("Grossbau GmbH", "grossbau"),
    ("Tiny Studio Co.", "tiny studio"),
    ("Acme Holdings Pvt. Ltd.", "acme holdings"),   # two suffixes, stripped both
])
def test_company_names_converge(raw, expected):
    assert normalize_company(raw) == expected


def test_normalize_company_handles_empty():
    assert normalize_company(None) is None
    assert normalize_company("   ") is None
    assert normalize_company("Inc.") is None      # suffix only -> nothing left


def test_invalid_emails_become_none_not_garbage():
    assert normalize_email("not-an-email") is None
    assert normalize_email("two@@at.com") is None
    assert normalize_email("  Dana@Example.COM ") == "dana@example.com"
    assert domain_of("bad") is None


def test_free_and_role_email_detection():
    assert is_business_email("m.okafor@helioscap.com")
    assert not is_business_email("sam_t99@gmail.com")
    assert is_role_email("info@brightpath.io")
    assert not is_role_email("dana@brightpath.io")


# --- scoring ---------------------------------------------------------------

def test_senior_business_lead_outranks_free_email_student():
    good = score_lead(Lead(email="m.okafor@helioscap.com", company="Helios",
                           title="Chief Technology Officer", employees=180,
                           country="Canada", source="referral"))
    bad = score_lead(Lead(email="sam_t99@gmail.com", title="Student",
                          country="India", source="newsletter"))
    assert good.score > bad.score
    assert good.band == "hot" and bad.band == "cold"


def test_score_is_fully_explainable():
    s = score_lead(Lead(email="dana@northwind.com", company="Northwind",
                        title="VP of Operations", employees=420,
                        country="United States", source="demo_request"))
    names = [n for n, _ in s.reasons]
    assert "business_email" in names and "title:vp" in names
    assert sum(v for _, v in s.reasons) == s.score   # nothing unaccounted for


def test_role_inbox_is_penalised_but_still_a_lead():
    s = score_lead(Lead(email="info@brightpath.io", company="BrightPath",
                        employees=90, country="United Kingdom",
                        source="contact_form"))
    assert ("role_email", -10) in s.reasons
    assert s.score > 0


def test_scores_are_clamped_to_0_100():
    assert score_lead(Lead(title="Student")).score == 0
    huge = score_lead(Lead(email="ceo@x.com", company="X", title="Founder CEO",
                           employees=500, country="US", source="referral"))
    assert huge.score <= 100


def test_weights_are_tunable_without_touching_code():
    lead = Lead(email="a@b.com", company="B")
    base = score_lead(lead).score
    tuned = score_lead(lead, weights={"business_email": 40}).score
    assert tuned == base + 20


def test_band_boundaries():
    assert band_for(34) == "cold" and band_for(35) == "warm"
    assert band_for(59) == "warm" and band_for(60) == "hot"


# --- dedupe ----------------------------------------------------------------

def test_same_company_different_spelling_collapses_to_best_record():
    a = score_lead(Lead(email="dana.ruiz@northwind-logistics.com",
                        company="Northwind Logistics, Inc.",
                        title="VP of Operations", employees=420,
                        country="United States", source="demo_request"))
    b = score_lead(Lead(email="d.ruiz@northwind-logistics.com",
                        company="Northwind Logistics LLC", employees=420))
    out = dedupe([a, b])
    assert len(out.kept) == 1
    assert out.kept[0].lead.title == "VP of Operations"   # richer record survived
    assert out.removed == 1


def test_free_email_falls_back_to_company_name_matching():
    a = score_lead(Lead(email="joe@gmail.com", company="Tiny Studio Co."))
    b = score_lead(Lead(email="jo@yahoo.com", company="TINY STUDIO"))
    assert len(dedupe([a, b]).kept) == 1


def test_unmatchable_leads_are_kept_not_silently_dropped():
    ghost = score_lead(Lead(title="Manager"))         # no email, no company
    out = dedupe([ghost])
    assert out.kept == [ghost] and out.removed == 0


def test_different_companies_are_not_merged():
    a = score_lead(Lead(email="x@alpha.com", company="Alpha"))
    b = score_lead(Lead(email="y@beta.com", company="Beta"))
    assert len(dedupe([a, b]).kept) == 2


# --- csv parsing ------------------------------------------------------------

def test_parse_accepts_the_column_names_crms_actually_use():
    lead = parse({"Work Email": "a@b.com", "Company Name": "B Inc",
                  "Job Title": "Head of Data", "Employee Count": "1,200",
                  "Country": "Canada", "utm_source": "referral"})
    assert lead.email == "a@b.com" and lead.company == "B Inc"
    assert lead.employees == 1200 and lead.title == "Head of Data"


def test_parse_survives_ranged_and_junk_employee_counts():
    assert parse({"employees": "50-200"}).employees == 50
    assert parse({"employees": "unknown"}).employees is None
    assert parse({"employees": ""}).employees is None


def test_seniority_matching_respects_word_boundaries():
    """'Director' contains 'cto'. Naive substring matching scores it C-level."""
    from leadscorer.score import seniority_points
    assert seniority_points("Director of Engineering") == ("title:director", 16)
    assert seniority_points("CTO") == ("title:cto", 25)
    assert seniority_points("Managerial Assistant") is None
    assert seniority_points("Warehouse Operative") is None

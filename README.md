# lead-scorer

Score, explain and deduplicate a lead list. Rule-based on purpose: every point
is attributable to a named rule, so when sales asks *why* a lead scored 72 the
answer is a list, not a shrug.

```
$ python cli.py examples/leads.csv --min-band warm
9 in, 1 duplicates merged, 6 at warm+

  m.okafor@helioscap.com    89 (hot): business_email +20, has_company +10, title:chief +22, size_50_1000 +15, target_country +10, inbound +12
  info@brightpath.io        57 (warm): business_email +20, role_email -10, has_company +10, size_50_1000 +15, target_country +10, inbound +12
```

## Why rules and not a model

For lead scoring specifically, an opaque model is usually the wrong trade. You
have few labels, the definition of "good lead" changes every quarter, and the
system only creates value if a sales team *trusts and acts on* the ranking. A
score they can audit gets worked. A score they can't gets ignored, and the
project gets written off as "AI didn't work for us".

Weights live in `DEFAULT_WEIGHTS` and are overridable per call - tune them
against closed-won data, keep the explanation.

```python
score_lead(lead, weights={"business_email": 40})
```

An LLM still earns its place here: enriching a title from a scraped bio,
classifying an open-text industry field. That is a normalization step feeding
these rules - not a replacement for them.

## The unglamorous half: normalization

Most lead-scoring disappointment is data quality wearing a model's clothes.

- `Northwind Logistics, Inc.` and `NORTHWIND LOGISTICS LLC` are one company.
  Legal suffixes are stripped **token-wise**, so `Vico` keeps its `co`.
- `holdings`, `group` and `partners` are deliberately *not* stripped - they
  carry meaning, and `Acme Holdings` may genuinely not be `Acme`.
- Free-mail domains are not company domains. `sam_t99@gmail.com` gets no
  business-email credit.
- `info@` / `sales@` are role inboxes: penalized, not discarded - at a 90-person
  company that address still reaches someone.
- A malformed email returns `None` rather than a plausible-looking wrong value.

Dedupe prefers the **domain** as identity and falls back to the normalized
company name, keeping the higher-scored record. Leads with neither are kept,
never silently dropped - a lead you cannot match is a data problem to fix, not a
row to lose.

## Two bugs worth naming

`"cto" in "Director of Engineering"` is `True`. Naive substring matching
promotes every engineering director to C-level. Seniority matching uses `\b`
boundaries and there is a test pinning it.

Per-record scoring is the easy half; the merge order is where duplicates get
lost. The richer record wins, and every merged address is reported in
`DedupeResult.merged` so a spot-check is possible.

## Use

```python
from leadscorer import parse, score_lead, dedupe

scored = [score_lead(parse(row)) for row in csv.DictReader(fh)]
result = dedupe(scored)
for s in sorted(result.kept, key=lambda s: -s.score):
    print(s.score, s.band, s.explain())
```

`parse()` accepts the column names CRMs actually export - `Work Email`,
`Company Name`, `Job Title`, `Employee Count`, `utm_source` - and survives
`50-200` and `unknown` in a numeric column.

`python -m pytest tests/` (21 tests, no dependencies) / MIT.

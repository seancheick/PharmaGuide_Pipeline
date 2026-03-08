# FDA API Reference

## openFDA Enforcement Endpoints

| Endpoint | What it covers |
|---|---|
| `https://api.fda.gov/food/enforcement.json` | Food & dietary supplement recalls |
| `https://api.fda.gov/drug/enforcement.json` | Drug recalls |
| `https://api.fda.gov/device/enforcement.json` | Medical device recalls (not used) |

## Date Range Query

```
GET https://api.fda.gov/food/enforcement.json
  ?search=report_date:[20260101+TO+20260307]
  &limit=100
  &skip=0
```

- `report_date` = when FDA published the enforcement record (YYYYMMDD format)
- `recall_initiation_date` = when the firm initiated the recall (use this for `regulatory_date`)
- Paginate with `skip` — max 100 per request, up to 1000 total
- 404 = no results for that date range (not an error)

## Key Fields for Our Use

| Field | Our mapping |
|---|---|
| `recall_number` | Citation in `jurisdictions[].source.citation` |
| `product_description` | Context for `reason` field |
| `reason_for_recall` | Primary text for substance extraction |
| `recalling_firm` | Context only (not stored in DB) |
| `classification` | Class I → critical, Class II → high, Class III → low |
| `recall_initiation_date` | Maps to `regulatory_date` (convert YYYYMMDD → YYYY-MM-DD) |
| `status` | "Ongoing" or "Terminated" — affects `match_mode` decision |
| `product_type` | "Food", "Drugs", "Dietary Supplement" — affects filtering |
| `distribution_pattern` | Context only |

## FDA Classification → clinical_risk_enum

| FDA Class | Meaning | Our `clinical_risk_enum` |
|---|---|---|
| Class I | Serious adverse health consequences or death | critical or high |
| Class II | May cause temporary adverse health consequences | moderate or high |
| Class III | Not likely to cause adverse consequences | low |

## Tainted Products Database (Manual)

For pharmaceutical adulterants in supplements, also check:
https://www.fda.gov/consumers/health-fraud-scams/tainted-products-marketed-dietary-supplements-medwatch

This database lists products found to contain undeclared drug ingredients. It is NOT available via openFDA API — must be checked manually for substances not caught by recall feed.

## MedWatch Safety Alerts

https://www.fda.gov/safety/medwatch-fda-safety-information-and-adverse-event-reporting-program

Sign up for email alerts at:
https://www.fda.gov/safety/medwatch/get-regular-fda-safety-updates

## Verification URLs

To verify a specific recall by number:
```
https://www.accessdata.fda.gov/scripts/ires/?action=Redirect&recall_number=<RECALL_NUMBER>
```

To search enforcement reports manually:
```
https://www.accessdata.fda.gov/scripts/ires/
```

## Rate Limits

- openFDA: No API key needed, but rate limited to 240 requests/minute
- With API key (free): 120,000 requests/day
- Register at: https://open.fda.gov/apis/authentication/
- Set env var `FDA_API_KEY` and the sync script will use it automatically

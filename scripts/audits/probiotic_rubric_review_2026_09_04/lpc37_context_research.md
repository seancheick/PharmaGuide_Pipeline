# Lpc-37: source review, not new clinical approval — 2026-09-04

This bounded review adds two single-strain human study contexts; it is not a
systematic review or a universal efficacy/dose recommendation. Two AI-assisted
source-review passes checked the original papers, including Sisu's full text
and ChillEx's Europe PMC fullTextXML; both titles/abstracts were also retrieved
using the existing NCBI efetch verifier. This is not human clinical approval.

## Sisu — [PMID 33385020](https://pubmed.ncbi.nlm.nih.gov/33385020/)

[Original full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC7770962/): 120
healthy adults aged 18–45, one capsule daily for five weeks. The primary
heart-rate response to an acute stress test was null in ITT and PP. Perceived
stress had a favorable secondary PP result; subgroup responses varied,
including opposite heart-rate directions by chronic-stress subgroup. These
are not positive primary efficacy or digestive-outcome findings.

Methods describe 17.5 billion CFU/capsule, while §3.2 distinguishes a 10-billion
target, 17.5-billion initial assay and 16.8-billion final assay. Store the
initial/final values as **measured viability**, not multiple dose arms or an
effective dose range. DuPont involvement and the missing baseline comparison
for the stress challenge limit interpretation.

## ChillEx — [PMID 37662485](https://pubmed.ncbi.nlm.nih.gov/37662485/)

[Original full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC10474370/): 190
healthy students aged 18–40, one capsule daily for ten weeks. The primary
week-eight state-anxiety comparison was null (P=.446). The first hierarchical
secondary test was also null, so subsequent sleep/alertness findings were
exploratory—not confirmed benefits. Participants did not develop the expected
degree of examination stress; the trial was industry-funded.

The 15.6-billion initial and 13.5-billion final CFU/capsule values are measured
viability of one regimen, not tested dose arms. No separate target amount was
established. The primary assessment at 56 days is distinct from the 70-day
intervention duration.

## Data boundaries

Keep the existing Sisu PMID and its historical review record, but correct
stale claims that the strain and dose were absent. The source's primary effect
is `null`; secondary findings remain explicitly lower in the context hierarchy.
Do not retain an implicit positive-primary default or generic immune-benefit
copy for these stress-response papers. Existing direction multipliers and all
pillar weights stay unchanged. ChillEx is a separately pending context, not
an automatically clinician-approved replacement scoring anchor.

Both contexts remain `source_verified_pending_clinical_review`. Their measured
viability cannot establish a label's clinical dose. More citations must not
become automatic approval, high confidence, or extra strain points.

## Old-artifact consistency

Independent review exposed stale indication copy in an otherwise correctly
joined older artifact. Three RED cases reproduced digestive/immune claims leaking
through primary indication, secondary indication, or a misused strength field.
The existing source assessment now carries registry-owned indication copy to
the descriptive alignment consumer; strength is not an indication. Label-row
objects, their ownership, review acceptance and dose remain unchanged. The
focused six-file backstop passed 233 tests, including input immutability and
unchanged null-result semantics. Full-corpus measurements are recorded in the
continuation execution summary, not inferred from these tests.

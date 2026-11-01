"""
Single-Source Normalization Module v1.0.0
==========================================
All pipeline stages MUST use this module for text normalization.
Ensures stable, reproducible normalized_key generation.

CRITICAL: Once a normalized_key is generated, it MUST NOT be recomputed.
Store it at entity creation time and propagate through all stages.
"""

import re
import math
import string
import unicodedata
from functools import lru_cache
from typing import Any, Iterable, Optional, Tuple

VERSION = "1.0.0"

# Declared assay units only; no conversion between assays or to enzyme mass.
# Shared by the cleaner, enrichment and the scoring-input contract.
ENZYME_ACTIVITY_UNITS = frozenset({
    "alu", "ppi", "blgu", "hut", "sapu", "spu", "fip", "cu", "gdu", "dppiv", "dpp-iv",
    "lacu", "fcc", "fccpu", "galu", "au", "skb", "mwu", "pu", "dp", "ckpu", "aju", "usp",
    "du", "pc", "agu", "bgu", "lu", "phy", "ftu", "su", "fu", "hcu", "hdu", "pgu", "endopgu", "xu", "sod",
})
_ENZYME_ACTIVITY_RE = re.compile(
    r"(?P<value>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>ALU|PPI|BLGU|HUT|SAPU|SPU|FIP|CU|GDU|DPP[- ]?IV|LACU|FCC(?:\s*\(\s*PU\s*\)|\s*PU|\s+lactase\s+units?)|GALU|AU|SKB|MWU|PU|DP|CKPU|AJU|USP|DU|PC|AGU|BGU|LU|PHY|FTU|SU|FU|HCU|HDU|ENDO[- ]?PGU|PGU|XU|SOD(?:\s+units?)?|fibrinolytic\s+units?)(?!\w)",
    re.IGNORECASE,
)


def extract_enzyme_activity(text, quantity=None, unit=None):
    """Read an explicit activity declaration without treating carrier mass as activity."""
    normalized_unit = re.sub(r"[\s()-]", "", str(unit or "").lower())
    if normalized_unit in {"sodunit", "sodunits"}:
        normalized_unit = "sod"
    try:
        value = float(str(quantity).replace(",", ""))
    except (TypeError, ValueError):
        value = None
    if normalized_unit in ENZYME_ACTIVITY_UNITS and value and math.isfinite(value) and value > 0:
        return value, "ENDO-PGU" if normalized_unit == "endopgu" else normalized_unit.upper()
    declaration = str(text or "")
    for match in _ENZYME_ACTIVITY_RE.finditer(declaration):
        # A potency per mass is not a serving activity. Preserve the label's
        # physical dose; do not infer activity by multiplying a concentration.
        if re.match(r"\s*(?:/|per\b)\s*(?:mg|g|kg|mcg|grams?|milligrams?|kilograms?)\b",
                    declaration[match.end():], re.IGNORECASE):
            continue
        value = float(match.group("value").replace(",", ""))
        if not math.isfinite(value) or value <= 0:
            continue
        unit_text = re.sub(r"[\s()-]", "", match.group("unit").upper())
        if unit_text == "ENDOPGU":
            unit_text = "ENDO-PGU"
        if unit_text.startswith("SOD"):
            unit_text = "SOD"
        if unit_text.startswith("FIBRINOLYTIC"):
            unit_text = "FU"
        elif unit_text.startswith("FCCLACTASE"):
            # The label explicitly names the lactase assay; retain its FCC
            # units without converting them to another assay or to mass.
            unit_text = "FCC"
        return value, unit_text
    return None, None

# Printed quantity qualifiers DSLD carries on a quantity's ``operator`` ("<1 g",
# "~33 mg"); "=" is an exact amount. The draft, console, importer and Clean
# accept only these, so a bound is never stored or shown as an exact amount.
QUANTITY_OPERATORS = frozenset({"<", "<=", ">", ">=", "~"})

_APPROXIMATE_COUNT_RE = re.compile(
    r"(?:about|approximately|approx\.?|~)\s*([0-9][0-9,]*(?:\.[0-9]+)?)", re.IGNORECASE)
# A comma is accepted only as US thousands grouping: "1,5" may be a decimal
# comma (1.5) and is never read as 15.
_GROUPED_COUNT_RE = re.compile(r"[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?")


def parse_servings_per_container(value: Any) -> Tuple[Optional[float], Optional[str]]:
    """Read a printed servings-per-container value.

    Returns ``(number, printed_text)``: the number is used for arithmetic, and
    ``printed_text`` keeps an approximation's wording ("about 17") so it is
    never presented as exact; it is None for a plain count. ``(None, None)``
    means the value cannot be read as a positive count.
    """
    if isinstance(value, bool):
        return None, None
    text = None
    if isinstance(value, str):
        stripped = value.strip()
        match = _APPROXIMATE_COUNT_RE.fullmatch(stripped)
        if match:
            text, value = stripped, match.group(1)
        value = str(value).strip()
        if "," in value:
            if not _GROUPED_COUNT_RE.fullmatch(value):
                return None, None
            value = value.replace(",", "")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, None
    if not math.isfinite(number) or number <= 0:
        return None, None
    # An approximation is a whole count ("about 17"); "about 1.5" is not read
    # as 1, and the integer export column never truncates it.
    if text is not None and not number.is_integer():
        return None, None
    return number, text


_MASS_UNIT_ALIASES = {
    "g": "g",
    "gm": "g",
    "gram": "g",
    "grams": "g",
    "mg": "mg",
    "milligram": "mg",
    "milligrams": "mg",
    "mcg": "mcg",
    # DSLD contains occasional transposed microgram tokens (for example,
    # Vitamin D ``25 mgc`` alongside its equivalent ``1,000 IU`` note).
    "mgc": "mcg",
    "ug": "mcg",
    "µg": "mcg",
    "μg": "mcg",
    "microgram": "mcg",
    "micrograms": "mcg",
}

FOLATE_FORM_FOLIC_ACID = "folic_acid"
FOLATE_FORM_METHYLFOLATE = "methylfolate"
FOLATE_FORM_FOLINIC = "folinic"
FOLATE_FORM_FOOD = "food_folate"
FOLATE_FORM_UNKNOWN = "unknown"


_OMEGA_MOLECULAR_FORM_PATTERNS = (
    ("phospholipid", re.compile(r"\b(phospholipid[s]?|phosphatidyl)\b", re.IGNORECASE)),
    ("re-esterified triglyceride", re.compile(
        r"\b(re[\s-]?esterified|reesterified|rtg|r-tg)\b",
        re.IGNORECASE,
    )),
    ("ethyl ester", re.compile(
        r"\b(ethyl\s+ester[s]?|fatty\s+acid\s+ethyl\s+ester[s]?|ee\s+form)\b",
        re.IGNORECASE,
    )),
    ("triglyceride", re.compile(
        r"\b(?:triglycerides?[\s-]+form|tg\s+form)\b|"
        r"^\s*(?:natural\s+)?triglycerides?(?:\s*\((?:mixed|unspecified)\))?\s*$|"
        r"(?:^|\n)\s*true\s+triglycerides?\s*(?:$|\n)|"
        r"\bas\s+(?:natural\s+)?triglycerides?\b|"
        r"\btriglycerides?,\s*natural\b|"
        r"\b(?:fish\s+oil|omega[\s-]*3\s+fatty\s+acids?|epa|dha|"
        r"eicosapentaenoic\s+acid|docosahexaenoic\s+acid)\s+triglycerides?\b|"
        r"\btriglyceride\s+algal\s+oil\b|"
        r"\bomega[\s-]*3\s+triglyceride\s+oil\b|"
        r"^\s*(?:triglyceride\s+fish\s+oil\b|omega[\s-]*3\s+(?:natural\s+)?triglycerides?\s+\d+(?:\.\d+)?\s*(?:mg|g)\b)|"
        r"\b(?:forms?\s*:\s*(?:from\s+)?|as\s+)(?:ethyl[\s-]+esters?|phospholipids?)"
        r"(?:\s|,|and|&)+triglycerides?\b|"
        r"\btriglycerides?\s*[,/&][^.;\n]{0,64}\b(?:omega[\s-]*3\s+)?forms?\b",
        re.IGNORECASE,
    )),
)
_OMEGA_MCT_CONTEXT = re.compile(
    r"\b(?:mct|c8|c10|medium[\s-]?chain|middle[\s-]?chain|caprylic|capric|coconut)"
    r"(?:[\s/-]+(?:capric|caprylic))*(?:\s+oil)?(?:\s+in(?:\s+the)?)?"
    r"[\s(-]+(?:natural\s+)?triglycerides?\b|"
    r"\btriglycerides?(?:[\s-]+form)?\s*\(\s*(?:mct|c8|c10)(?:\s+oil)?\s*\)",
    re.IGNORECASE,
)


def omega_molecular_form_disclosures(surfaces: Iterable[str]) -> Tuple[str, ...]:
    """Return distinct molecular-form tokens disclosed by label text.

    This is the shared label-language decision used by enrichment and by
    presentation metadata. It does not assign quality points. Enrichment still
    resolves the returned token inside each already-known IQM parent, and IQM
    remains the sole owner of form quality.

    MCT carrier wording and blood-lipid claims are not fish-oil
    molecular-form evidence. The singular wrapper below fails closed when
    these tokens describe more than one global form.
    """
    detected = set()
    for raw_surface in surfaces:
        surface = str(raw_surface or "")
        if not surface:
            continue
        for token, pattern in _OMEGA_MOLECULAR_FORM_PATTERNS:
            candidate = surface
            if token == "triglyceride":
                # Require affirmative form wording, never a bare mention in
                # health prose. Remove only the MCT noun phrase so a separate
                # fish-oil form disclosure remains available.
                candidate = _OMEGA_MCT_CONTEXT.sub(" ", candidate)
            if pattern.search(candidate):
                detected.add(token)
    return tuple(
        token for token, _ in _OMEGA_MOLECULAR_FORM_PATTERNS if token in detected
    )


def omega_molecular_form_disclosure(surfaces: Iterable[str]) -> Optional[str]:
    """Return the disclosure only when the label proves one global form.

    Enrichment uses this singular contract so a mixed-form label cannot stamp
    one form onto every omega row. Presentation code may inspect the ordered
    plural result without assigning quality from it.
    """
    detected = omega_molecular_form_disclosures(surfaces)
    # rTG is a specific kind of triglyceride, and labels commonly print both
    # in one phrase ("Triglyceride Form [TG as rTG]"). That is one form, not a
    # conflicting mixed-form disclosure.
    if set(detected) == {"re-esterified triglyceride", "triglyceride"}:
        return "re-esterified triglyceride"
    return detected[0] if len(detected) == 1 else None


@lru_cache(maxsize=128)
def canonicalize_mass_unit(unit: str) -> str:
    """Return the canonical ``g``/``mg``/``mcg`` token for known aliases."""
    if not unit:
        return ""
    normalized = unicodedata.normalize("NFKC", str(unit)).lower().strip().rstrip(".")
    normalized = re.sub(r"\(s\)$", "s", normalized)
    return _MASS_UNIT_ALIASES.get(normalized, normalized)

_NUTRIENT_ACTIVITY_UNITS = {
    "mcgrae": "mcg rae",
    "mcgdfe": "mcg dfe",
    "mgdfe": "mg dfe",
    "mgne": "mg ne",
}

# Units that name WHICH analyte the milligrams measure rather than rescaling
# one substance into another. FDA vitamin E amounts are mg alpha-tocopherol,
# DSLD also spells that "mg AT"; the enricher treats both as mg the same way.
# The analyte's canonical parent is kept so only that nutrient may use them.
_ANALYTE_QUALIFIED_MASS_UNITS = {
    "mgat": ("mg", "vitamin_e"),
    "mgalpha-tocopherol": ("mg", "vitamin_e"),
    "mgalphatocopherol": ("mg", "vitamin_e"),
}


def analyte_unit_parent(unit: str) -> Optional[str]:
    """Canonical parent an analyte-qualified unit belongs to, else None."""
    entry = _ANALYTE_QUALIFIED_MASS_UNITS.get(re.sub(r"[\s_]+", "", str(unit or "").lower()))
    return entry[1] if entry else None


def canonicalize_nutrient_unit(unit: str) -> str:
    """Canonical mass token, or the spaced activity unit (``mcg dfe``, ``mg ne``).

    Analyte-qualified mass (``mg alpha-tocopherol``, ``mg AT``) is plain ``mg``.

    Enriched rows spell activity units without spaces (``mcgdfe``) while
    reference data spells them with spaces; both map to one token here.
    """
    compact = re.sub(r"[\s_]+", "", str(unit or "").lower())
    analyte = _ANALYTE_QUALIFIED_MASS_UNITS.get(compact)
    return _NUTRIENT_ACTIVITY_UNITS.get(compact) or (analyte and analyte[0]) or canonicalize_mass_unit(unit)


# Pre-built translation table for smart quotes, primes, and apostrophe variants.
# Built once at module load — used by normalize_text() on every uncached call.
# Includes prime characters (U+2032/2033) for chemical nomenclature
# (e.g., riboflavin-5'-phosphate) and modifier letter apostrophe (U+02BC).
_QUOTE_TRANS = str.maketrans({
    chr(cp): "'" for cp in (0x2018, 0x2019, 0x201A, 0x201B, 0x2032, 0x2033, 0x02BC)
} | {
    chr(cp): '"' for cp in (0x201C, 0x201D, 0x201E, 0x201F)
})


@lru_cache(maxsize=65536)
def normalize_text(raw: str) -> str:
    """
    Standard text normalization for display and fuzzy matching.

    Operations (in order):
    1. Unicode NFC normalization
    2. Lowercase
    3. Strip leading/trailing whitespace
    4. Greek beta (β) → 'beta' in supplement contexts
    5. Micro sign (µg) → 'mcg'
    6. Em-dash/en-dash → regular hyphen
    7. Normalize numeric slashes (1/2 → 1 2)
    8. Commas, middle dots → space
    9. Trademark/copyright symbols removed
    10. Collapse internal whitespace

    Returns: normalized string for matching

    This function consolidates logic from:
    - enrich_supplements_v3.py:_normalize_text (lines 673-721)
    """
    if not raw:
        return ""

    # Unicode NFC normalization
    text = unicodedata.normalize('NFC', raw)

    # Lowercase and strip
    text = text.lower().strip()

    # Normalize smart quotes/apostrophes/primes to ASCII equivalents
    text = text.translate(_QUOTE_TRANS)

    # Normalize Greek letters (α, β, γ, δ) to Latin equivalents
    # Used in vitamin forms: α-tocopherol, β-carotene, γ-tocopherol, δ-tocopherol
    # and supplement compounds: β-glucan, β-sitosterol, β-alanine, etc.

    # Alpha (U+03B1)
    text = re.sub(r'α-(tocopherol|tocopheryl|lipoic|linolenic|lactalbumin|casein|galactosidase|amylase|ketoglutarate|gpc|cyclodextrin)',
                  r'alpha-\1', text)
    text = re.sub(r'\bα\b', 'alpha', text)

    # Beta (U+03B2)
    text = re.sub(r'β-(glucan|carotene|sitosterol|alanine|hydroxy|cryptoxanthin|elemene|caryophyllene|myrcene)',
                  r'beta-\1', text)
    text = re.sub(r'\bβ\b', 'beta', text)
    text = re.sub(r'β glucan', 'beta glucan', text)

    # Gamma (U+03B3)
    text = re.sub(r'γ-(tocopherol|tocopheryl|linolenic|oryzanol|aminobutyric|butyrolactone)',
                  r'gamma-\1', text)
    text = re.sub(r'\bγ\b', 'gamma', text)

    # Delta (U+03B4)
    text = re.sub(r'δ-(tocopherol|tocopheryl|tocotrienol)',
                  r'delta-\1', text)
    text = re.sub(r'\bδ\b', 'delta', text)

    # Normalize micro sign: ONLY before gram units (µg, µgram)
    text = re.sub(r'µg\b', 'mcg', text)
    text = re.sub(r'µgram', 'mcgram', text)

    # Normalize dashes: em-dash (—), en-dash (–) → regular hyphen
    text = re.sub(r'[—–]', '-', text)

    # Normalize numeric slashes: "1/2" or "1 / 2" → "1 2"
    text = re.sub(r'(\d)\s*/\s*(\d)', r'\1 \2', text)

    # Normalize commas and middle dots to spaces (for patterns like "1,3/1,6")
    text = re.sub(r'[,\u00B7]', ' ', text)

    # Remove trademark symbols
    text = re.sub(r'[™®©]', '', text)
    # Also remove parenthesized mark tokens that frequently survive OCR/vendor exports
    text = re.sub(r'\((?:tm|r|c)\)', '', text)

    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


@lru_cache(maxsize=1024)
def classify_folate_form(raw: str) -> str:
    """Classify label-explicit folate lineage without assigning a DFE factor.

    This is the shared identity decision used by conversion and UL scoping.
    Conversion remains a separate policy: a recognized reduced folate such as
    folinic acid can be identified here while still having no authorized
    mass-to-DFE conversion rule.
    """
    text = normalize_text(str(raw or ""))
    if re.search(r"\bfolic\s+acid\b", text):
        return FOLATE_FORM_FOLIC_ACID
    if re.search(
        r"\b(?:methylfolate|methyltetrahydrofolate|"
        r"methyltetrahydrofolic\s+acid|5[-\s]?mthf|metafolin|quatrefolic)\b",
        text,
    ):
        return FOLATE_FORM_METHYLFOLATE
    if re.search(r"\b(?:folinic(?:\s+acid)?|folinate|leucovorin)\b", text):
        return FOLATE_FORM_FOLINIC
    if re.search(
        r"\b(?:(?:food|natural)\s+folate|(?:organic\s+)?food\s+blend)\b",
        text,
    ):
        return FOLATE_FORM_FOOD
    return FOLATE_FORM_UNKNOWN


# DSLD writes "0" or "1" for "no UNII assigned".
UNII_PLACEHOLDERS = frozenset({"", "0", "1"})


def normalize_unii(value: Any) -> Optional[str]:
    """Canonicalize a UNII string. Returns None for placeholders/garbage.

    The one UNII normalizer: the cleaner's index build and lookups, the
    enricher and the api_audit UNII tools all call it. FDA UNIIs are exactly
    10 alphanumeric characters. DSLD raw labels and reference data may emit
    them with whitespace or mixed case, and DSLD uses "0" and "1" as
    placeholders. Strip whitespace, uppercase, and reject placeholders and
    malformed values.

    Returns:
        Optional[str]: 10-char uppercase alphanumeric UNII, or None.
    """
    if not isinstance(value, str):
        return None
    canon = value.strip().upper()
    if not canon or canon in UNII_PLACEHOLDERS:
        return None
    if len(canon) != 10 or not canon.isalnum():
        return None
    return canon


@lru_cache(maxsize=65536)
def make_normalized_key(raw: str) -> str:
    """
    Generate a stable, deterministic key for deduplication and tracking.

    Operations (beyond normalize_text):
    1. Apply normalize_text()
    2. Remove ALL punctuation except hyphens
    3. Replace spaces and hyphens with underscores
    4. Collapse multiple underscores
    5. Strip leading/trailing underscores

    Returns: immutable key string (e.g., "vitamin_b12_methylcobalamin")

    CRITICAL: Once generated, normalized_key MUST NOT be recomputed.
    Store it at entity creation time.

    Examples:
        "Vitamin B12" → "vitamin_b12"
        "Vitamin B12 (as Methylcobalamin)" → "vitamin_b12_as_methylcobalamin"
        "β-Glucan" → "beta_glucan"
        "1,000 mcg" → "1_000_mcg"
    """
    if not raw:
        return ""

    # Start with standard normalization
    text = normalize_text(raw)

    # Remove parentheses but keep contents
    text = re.sub(r'[()]', ' ', text)

    # Remove brackets but keep contents
    text = re.sub(r'[\[\]]', ' ', text)

    # Preserve semantic separators as token boundaries before removing the
    # remaining punctuation. Deleting them joined distinct identities
    # (``10:1`` -> ``101`` and ``D/K2`` -> ``dk2``).
    text = re.sub(r'[:/]', ' ', text)

    # Remove all remaining punctuation except hyphens.
    # Keep alphanumeric, hyphens, and spaces.
    text = re.sub(r'[^\w\s-]', '', text)

    # Replace spaces and hyphens with underscores
    text = re.sub(r'[\s-]+', '_', text)

    # Collapse multiple underscores
    text = re.sub(r'_+', '_', text)

    # Strip leading/trailing underscores
    text = text.strip('_')

    return text


@lru_cache(maxsize=5000)
def normalize_company_name(name: str) -> str:
    """
    Normalize company name for manufacturer matching.

    Additional operations beyond normalize_text:
    - Remove corporate suffixes (LLC, Inc, Corp, etc.)
    - Handle special characters in brand names

    Returns: normalized company name for matching

    Examples:
        "Garden of Life LLC" → "garden of life"
        "NOW Foods, Inc." → "now foods"
    """
    if not name:
        return ""

    # Apply standard normalization first
    name = normalize_text(name)

    # Remove common corporate suffixes
    # Order matters: longer suffixes first to prevent partial matches
    suffixes_pattern = (
        r'\s*,?\s*('
        r'l\.l\.c\.|llc|'
        r'incorporated|inc\.?|'
        r'corporation|corp\.?|'
        r'company|co\.?|'
        r'limited|ltd\.?|'
        r'plc|gmbh|ag|sa|nv|bv|pty|pvt'
        r')\.?\s*$'
    )
    name = re.sub(suffixes_pattern, '', name, flags=re.IGNORECASE)

    return name.strip()


@lru_cache(maxsize=5000)
def normalize_for_skip_matching(name: str) -> str:
    """
    Tier B normalization for skip set matching.
    Minimal transformation to preserve specificity.

    Operations:
    1. Unicode NFC normalization
    2. Strip whitespace
    3. Collapse internal whitespace

    Does NOT lowercase or remove punctuation.
    Used for matching against skip sets where case and punctuation matter.

    This preserves the logic from:
    - enhanced_normalizer.py:_normalize_for_skip (lines 1418-1439)
    """
    if not name:
        return ""

    # NFC normalization
    normalized = unicodedata.normalize('NFC', name)

    # Trim whitespace
    normalized = normalized.strip()

    # Collapse internal whitespace to single space
    normalized = re.sub(r'\s+', ' ', normalized)

    return normalized


@lru_cache(maxsize=5000)
def preprocess_text(text: str) -> str:
    """
    Comprehensive text preprocessing for ingredient matching.
    Used by EnhancedDSLDNormalizer for initial ingredient processing.

    Operations:
    1. Lowercase + strip
    2. Remove parenthetical information
    3. Remove brackets and contents
    4. Remove curly braces (keep contents)
    5. Remove trademark symbols
    6. Strip punctuation at ends
    7. Collapse whitespace
    8. Remove common prefixes (dl-, d-, l-, natural, synthetic, organic)
    9. Remove common suffixes (extract, powder, oil, concentrate)

    This preserves the logic from:
    - enhanced_normalizer.py:preprocess_text (lines 225-278)
    """
    if not text:
        return ""

    # Start from the shared normalizer so punctuation and quote variants resolve
    # consistently across clean and enrich stages.
    text = normalize_text(text)

    # Remove common parenthetical information
    text = re.sub(r'\([^)]*\)', '', text)

    # Remove brackets and their contents
    text = re.sub(r'\[[^\]]*\]', '', text)

    # Remove curly braces but keep their contents
    text = re.sub(r'[{}]', '', text)

    # Remove trademark symbols
    text = re.sub(r'[™®©]', '', text)

    # Remove extra whitespace and punctuation at ends
    text = text.strip(string.punctuation + string.whitespace)

    # Normalize multiple spaces
    text = re.sub(r'\s+', ' ', text)

    # Remove common prefixes that don't affect matching.
    # Apply iteratively so compound prefixes like "raw organic" are fully normalized.
    # NOTE: 'dl-', 'd-', 'l-' are stereoisomer prefixes that ARE meaningful for
    # vitamin E forms (d-alpha vs dl-alpha tocopherol) and some amino acids.
    # We guard against stripping them when followed by alpha/beta/gamma/delta
    # (tocopherol stereoisomers) to preserve matching fidelity.
    # Guard stereoisomer prefixes for tocopherols AND amino acids/sugars
    # d-/l-/dl- prefixes are chemically meaningful for these compounds
    _stereo_guard = re.compile(
        r'^[dl]l?-(alpha|beta|gamma|delta'
        r'|mannose|ribose|theanine|carnitine|glutamine|glutathione'
        r'|methionine|phenylalanine|tryptophan|tyrosine|leucine'
        r'|isoleucine|valine|lysine|arginine|histidine|cysteine|cystine'
        r'|serine|threonine|alanine|proline|asparagine|aspartate'
        r'|limonene|pinitol|chiro|glucarate|pantothenate'
        r'|calcium|malic|tartrate'
        r'|biotin|selenomethionine|methylfolate|methyltetrahydro'
        r'|saccharic|galactose|glucose|fructose|tagatose)\b'
    )
    prefixes_to_remove = [
        'dl-', 'd-', 'l-',
        'natural ', 'synthetic ', 'organic ',
        'raw ', 'wild crafted ', 'wild-crafted ', 'wildcrafted '
    ]
    changed = True
    while changed:
        changed = False
        for prefix in prefixes_to_remove:
            if text.startswith(prefix):
                # Guard: don't strip d-/dl-/l- before tocopherol stereoisomers
                if prefix in ('dl-', 'd-', 'l-') and _stereo_guard.match(text):
                    continue
                text = text[len(prefix):].strip()
                changed = True
                break

    # Loop suffix removal to handle multiple suffixes like "Extract, Powder".
    # Do not strip "oil": it is chemically meaningful for identities such as
    # fish oil, cod liver oil, oregano oil, krill oil, and MCT oil.
    suffixes_to_remove = [' extract', ' powder', ' concentrate']
    changed = True
    while changed:
        changed = False
        # Strip punctuation first
        text = text.strip(string.punctuation + string.whitespace)
        for suffix in suffixes_to_remove:
            if text.endswith(suffix):
                text = text[:-len(suffix)]
                changed = True
                break

    # Final cleanup
    text = text.strip(string.punctuation + string.whitespace)

    return text.strip()


@lru_cache(maxsize=5000)
def descriptor_fallback_candidates(text: str, *, purpose_only: bool = False) -> Tuple[str, ...]:
    """
    Generate late-stage fallback candidates by stripping common label descriptors.

    This is intentionally narrower than preprocess_text(). It is used only after
    exact/raw matching misses, so we can recover labels like:
    - "Cold-Pressed Lemon Oil" -> "lemon oil"
    - "Beeswax, Natural" -> "beeswax"
    - "Coconut Oil, Extra Virgin" -> "coconut oil"
    """
    if not text:
        return ()

    base = normalize_text(text).strip(string.punctuation + string.whitespace)
    if not base:
        return ()

    leading_descriptors = (
        "100% ",
        "cold-pressed ",
        "cold pressed ",
        "certified organic ",
        "organic ",
        "extra virgin ",
        "pharmaceutical grade ",
        "molecularly distilled ",
        "highly purified and concentrated ",
        "highly purified ",
        "purified ",
        "pure ",
        "natural ",
        "deionized ",
    )
    trailing_descriptors = (
        " extra virgin",
        " natural",
        " purified",
        " pure",
        " deionized",
    )

    seen = {base}
    queue = [base]
    candidates = []
    # A stated colorant purpose is not a preparation or extra ingredient.
    # Keep composition-bearing parentheses intact; exact matching precedes
    # this narrowly scoped fallback at every consumer.
    purpose_stripped = re.sub(
        r"\s*\(for colou?r\)$", "", normalize_text(text).strip()
    ).strip(string.punctuation + string.whitespace)
    if purpose_stripped and purpose_stripped != base:
        seen.add(purpose_stripped)
        candidates.append(purpose_stripped)
        queue.append(purpose_stripped)

    if purpose_only:
        return tuple(candidates)

    while queue:
        current = queue.pop(0).strip(string.punctuation + string.whitespace)
        if not current:
            continue

        for prefix in leading_descriptors:
            if current.startswith(prefix):
                candidate = current[len(prefix):].strip(string.punctuation + string.whitespace)
                if candidate and candidate not in seen:
                    seen.add(candidate)
                    candidates.append(candidate)
                    queue.append(candidate)

        for suffix in trailing_descriptors:
            if current.endswith(suffix):
                candidate = current[: -len(suffix)].strip(string.punctuation + string.whitespace)
                if candidate and candidate not in seen:
                    seen.add(candidate)
                    candidates.append(candidate)
                    queue.append(candidate)

    return tuple(candidates)


@lru_cache(maxsize=5000)
def strip_extraction_noise(text: str) -> str:
    """
    Strip extraction/dosage noise prefixes from ingredient names.

    Handles patterns commonly found in supplement labels where the actual
    ingredient is buried after dosage or sourcing information:

    - "providing X mg of Y" → "Y"
    - "providing X mg Y" → "Y"
    - "from X mg of Y" → "Y"
    - "from X mg Y" → "Y"
    - "min. X mg Y" → "Y"
    - "minimum X mg Y" → "Y"
    - "Contains X mg of Y" → "Y"
    - "yielding X mg of Y" → "Y"
    - "standardized to X% Y" → "Y"
    - "standardized for X mg Y" → "Y"
    - "supplying X mg of Y" → "Y"
    - "delivering X mg of Y" → "Y"

    Examples:
        "Fish Oil (providing 180 mg of EPA)" → "EPA"
        "from 500 mg of Green Tea Extract" → "Green Tea Extract"
        "standardized to 95% curcuminoids" → "curcuminoids"
        "min. 50 mg silymarin" → "silymarin"

    Returns: cleaned ingredient name with noise stripped
    """
    if not text:
        return ""

    # Work on lowercased version for pattern matching
    lower_text = text.lower().strip()

    # Patterns to strip (order matters - more specific first)
    # Each pattern captures the meaningful ingredient at the end
    extraction_patterns = [
        # "providing X mg/mcg/g of Y" or "providing X mg/mcg/g Y"
        r'^.*?providing\s+[\d,.]+\s*(?:mg|mcg|g|iu|µg)\s+(?:of\s+)?(.+)$',
        # "from X mg/mcg/g of Y" or "from X mg/mcg/g Y"
        r'^.*?from\s+[\d,.]+\s*(?:mg|mcg|g|iu|µg)\s+(?:of\s+)?(.+)$',
        # "yielding X mg/mcg/g of Y" or "yielding X mg/mcg/g Y"
        r'^.*?yielding\s+[\d,.]+\s*(?:mg|mcg|g|iu|µg)\s+(?:of\s+)?(.+)$',
        # "supplying X mg/mcg/g of Y" or "supplying X mg/mcg/g Y"
        r'^.*?supplying\s+[\d,.]+\s*(?:mg|mcg|g|iu|µg)\s+(?:of\s+)?(.+)$',
        # "delivering X mg/mcg/g of Y" or "delivering X mg/mcg/g Y"
        r'^.*?delivering\s+[\d,.]+\s*(?:mg|mcg|g|iu|µg)\s+(?:of\s+)?(.+)$',
        # "contains X mg/mcg/g of Y" or "containing X mg/mcg/g Y"
        r'^.*?contain(?:s|ing)\s+[\d,.]+\s*(?:mg|mcg|g|iu|µg)\s+(?:of\s+)?(.+)$',
        # "min. X mg Y" or "minimum X mg Y"
        r'^.*?(?:min\.?|minimum)\s+[\d,.]+\s*(?:mg|mcg|g|iu|µg)\s+(?:of\s+)?(.+)$',
        # "standardized to X% Y"
        r'^.*?standardized\s+to\s+[\d,.]+\s*%\s+(?:of\s+)?(.+)$',
        # "standardized for X mg Y"
        r'^.*?standardized\s+for\s+[\d,.]+\s*(?:mg|mcg|g|iu|µg)\s+(?:of\s+)?(.+)$',
        # "equivalent to X mg of Y"
        r'^.*?equivalent\s+to\s+[\d,.]+\s*(?:mg|mcg|g|iu|µg)\s+(?:of\s+)?(.+)$',
        # "with X mg of Y"
        r'^.*?with\s+[\d,.]+\s*(?:mg|mcg|g|iu|µg)\s+(?:of\s+)?(.+)$',
    ]

    for pattern in extraction_patterns:
        match = re.match(pattern, lower_text, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            # Remove trailing punctuation and parentheses
            extracted = extracted.rstrip('.,;:()[]')
            if extracted:
                return extracted

    # No pattern matched, return original (stripped)
    return text.strip()


def validate_normalized_key(key: str) -> Tuple[bool, str]:
    """
    Validate that a string is a valid normalized_key format.

    Valid keys:
    - Only contain lowercase letters, numbers, and underscores
    - Do not start or end with underscores
    - Do not contain consecutive underscores

    Returns: (is_valid, error_message_or_empty)
    """
    if not key:
        return False, "empty key"

    # Check for valid characters
    if not re.match(r'^[a-z0-9_]+$', key):
        return False, "contains invalid characters (only a-z, 0-9, _ allowed)"

    # Check for leading/trailing underscores
    if key.startswith('_') or key.endswith('_'):
        return False, "starts or ends with underscore"

    # Check for consecutive underscores
    if '__' in key:
        return False, "contains consecutive underscores"

    return True, ""


def normalize_exact_text(text: str) -> str:
    """
    Minimal normalization for exact matching.
    Only lowercase and trim to preserve punctuation and symbols.

    Used when punctuation-sensitive matching is needed.
    """
    if not text:
        return ""
    return text.strip().lower()


# Module-level cache clear function for testing
def clear_caches():
    """Clear all LRU caches. Useful for testing."""
    normalize_text.cache_clear()
    make_normalized_key.cache_clear()
    normalize_company_name.cache_clear()
    normalize_for_skip_matching.cache_clear()
    preprocess_text.cache_clear()
    strip_extraction_noise.cache_clear()


# D2.2: common qualifier tokens that describe PREPARATION or processing,
# not ingredient identity. Stripping them from the tail of a name
# recovers the canonical form — "Phenylalanine, Micronized" resolves
# to the same canonical as "Phenylalanine", "Quercetin, Organic" to
# "Quercetin", etc.
_QUALIFIER_SUFFIX_RE = re.compile(
    r",\s*("
    r"micronized|organic|natural|freeze[- ]dried|raw|fermented|vegan|"
    r"non[- ]gmo|usp|pharmaceutical[- ]grade|food[- ]grade|"
    r"certified[- ]organic|whole[- ]leaf|kosher|halal|powder"
    r")\s*$",
    re.IGNORECASE,
)

# D2.7.3: leading percent prefix stripped on fallback. "88% organic whole
# leaf Aloe vera" → "organic whole leaf Aloe vera" → (then leading-adjective
# strip) → "Aloe vera". Stripped version is tried as a fallback lookup so
# real standardization-marker rows (already excluded by
# _is_nutrition_fact) aren't affected.
_LEADING_PERCENT_PREFIX_RE = re.compile(
    r"^\s*\d+(?:\.\d+)?\s*%\s*",
)

# D2.7.3: leading adjective prefixes that describe SOURCE QUALITY or
# PROCESSING but not ingredient identity. Stripped iteratively after
# the percent prefix is removed.
_LEADING_ADJECTIVE_RE = re.compile(
    r"^\s*(organic|certified\s+organic|natural|raw|pure|whole[- ]leaf|"
    r"whole[- ]plant|whole[- ]herb|non[- ]gmo|fermented|freeze[- ]dried|"
    r"standardized|concentrated|micronized|cold[- ]pressed|unrefined)\s+",
    re.IGNORECASE,
)

# D2.7.3: common trailing descriptor suffix — DSLD sometimes emits
# "Curcumin Phytosome:" or "Fenugreek Extract :" with trailing colon.
_TRAILING_COLON_RE = re.compile(r"\s*[:;]\s*$")

def strip_label_identity_qualifiers(name: str) -> str:
    """
    Remove trailing preparation/processing qualifier tokens from an
    ingredient name (D2.2 + D2.7.3 extensions).

    Strips in order:
      1. Trailing colon/semicolon (DSLD parsing artifact)
      2. `, Micronized` / `, Organic` / `, Powder` / etc.
      3. Leading `N%` prefix (e.g., "88% organic aloe vera")

    Applied only on the FALLBACK lookup path — does not override an
    exact raw-name or standard-name hit. Regex anchored to prevent
    mid-name corruption.
    """
    if not name:
        return name
    result = _TRAILING_COLON_RE.sub("", name).strip()
    # Apply comma-qualifier strip repeatedly until stable (handles
    # ", Powder, Organic" chains).
    for _ in range(3):
        stripped = _QUALIFIER_SUFFIX_RE.sub("", result).strip()
        if stripped == result:
            break
        result = stripped
    # Strip leading percent prefix (D2.7.3: "88% organic aloe vera" →
    # "organic aloe vera").
    result = _LEADING_PERCENT_PREFIX_RE.sub("", result).strip()
    # Strip leading adjective prefixes iteratively (D2.7.3: "organic
    # whole leaf aloe vera" → "whole leaf aloe vera" → "aloe vera").
    for _ in range(4):
        stripped = _LEADING_ADJECTIVE_RE.sub("", result).strip()
        if stripped == result:
            break
        result = stripped
    return result


def is_negated_match_phrase(text: str, matched_term: str, *, spaced_free: bool = False) -> bool:
    """Recognize explicit negation around a term; shared label-text predicate.

    ``spaced_free`` also reads "Dairy Free" as negation. Callers matching
    substance names leave it off: "free base" is chemistry, not absence.
    """
    term = (matched_term or "").strip().lower()
    if not text or not term:
        return False

    text_lower = text.lower()
    escaped_term = re.escape(term)
    negation_patterns = (
        rf"\b{escaped_term}\s*{'-?' if spaced_free else '-'}\s*free\b",
        rf"\bfree\s+from\s+{escaped_term}\b",
        rf"\bcontains?\s+no\s+{escaped_term}\b",
        rf"\bno\s+{escaped_term}\b",
        rf"\bwithout\s+{escaped_term}\b",
        rf"\bnon[-\s]+{escaped_term}\b",
    )
    return any(re.search(pattern, text_lower) for pattern in negation_patterns)


def find_affirmative_label_match(pattern, text: str, *, spaced_free: bool = False):
    """Return an affirmative occurrence, preserving clause/list negation.

    Identity callers can include spaced absence claims while retaining chemical
    free-base/form/acid wording and positive "fish oil free of contaminants"
    qualifiers. Existing callers keep their previous semantics.
    """
    for clause in re.split(r"[.;!?\r\n]+|\b(?:but|however)\b", text, flags=re.I):
        for candidate in pattern.finditer(clause):
            term = candidate.group(0)
            if spaced_free:
                qualifier = re.match(r"[-\s]+free[-\s]+(?:base|form|acid|of|from)\b",
                                     clause[candidate.end():], re.I)
                if qualifier:
                    term += qualifier.group(0)
            if is_negated_match_phrase(clause, term, spaced_free=spaced_free):
                continue
            if re.search(r"\b(?:no|not|without|free\s+(?:of|from))\b", clause[:candidate.start()], re.I):
                continue
            return candidate
    return None

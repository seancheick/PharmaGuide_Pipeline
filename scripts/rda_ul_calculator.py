#!/usr/bin/env python3
"""
RDA/UL Adequacy Calculator Module

Computes nutrient adequacy scores based on RDA/AI, optimal ranges, and UL values.
Outputs structured evidence for scoring consumption.

Key features:
- RDA/AI percentage calculation
- UL comparison with safety flags
- Adequacy band classification
- "No UL" policy handling
- Full evidence tracking

Usage:
    from rda_ul_calculator import RDAULCalculator

    calculator = RDAULCalculator()
    result = calculator.compute_nutrient_adequacy(
        nutrient="Vitamin D3",
        amount=50,
        unit="mcg"
    )
"""

import json
import re
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Any, Union

from normalization import canonicalize_mass_unit

logger = logging.getLogger(__name__)


UL_REVIEW_FOLATE_FORM = "FOLATE_UL_FORM_REVIEW"
UL_REVIEW_MAGNESIUM_SOURCE = "MAGNESIUM_UL_SOURCE_REVIEW"
_UL_REVIEW_SIGNALS = {
    "unknown_folate_form_lineage": UL_REVIEW_FOLATE_FORM,
    "supplemental_magnesium_fraction_unknown": UL_REVIEW_MAGNESIUM_SOURCE,
}


def get_actionable_ul_review_signals(rda_ul_data: Any) -> List[str]:
    """Return stable review signals from the shared RDA/UL review contract."""
    if not isinstance(rda_ul_data, dict):
        return []
    signals: List[str] = []
    flags = rda_ul_data.get("ul_review_flags")
    if not isinstance(flags, list):
        return signals
    for flag in flags:
        if not isinstance(flag, dict) or flag.get("review_required") is not True:
            continue
        assessment = str(flag.get("assessment_status") or "").strip().lower()
        signal = _UL_REVIEW_SIGNALS.get(str(flag.get("reason") or "").strip().lower())
        if assessment == "indeterminate" and signal and signal not in signals:
            signals.append(signal)
    return signals


# Adequacy bands per spec
ADEQUACY_BANDS = {
    "deficient": {"min_pct": 0, "max_pct": 25, "points": 0},
    "suboptimal": {"min_pct": 25, "max_pct": 75, "points": 1},
    "optimal": {"min_pct": 75, "max_pct": 150, "points": 3},
    "high": {"min_pct": 150, "max_pct": 300, "points": 2},
    "excessive": {"min_pct": 300, "max_pct": float('inf'), "points": 0}
}


# Mass-unit reconciliation. rda_ai/ul are stored in each nutrient's own table
# `unit`; the label amount can arrive in a different mass unit (mcg vs mg)
# because unit_converter.convert_nutrient is a no-op for plain minerals. These
# support converting the label amount into the table unit before any pct math.
_MASS_TO_MCG = {"g": 1_000_000.0, "mg": 1_000.0, "mcg": 1.0}


def ul_display_severity(pct_ul: Any) -> str:
    """Display severity for an exposure that already exceeds its UL.

    Twice the limit (200%) is ``critical``. Every lower percentage is
    ``warning``. This is only that display word. It is not the 100%
    confirmed-exceedance test, the 150% quality-score deduction, or the
    personalized 80% approaching-UL tier.
    """
    if isinstance(pct_ul, bool):
        pct = 0.0
    else:
        try:
            pct = float(pct_ul)
        except (TypeError, ValueError):
            pct = 0.0
        if not math.isfinite(pct):
            pct = 0.0
    return "critical" if pct >= 200.0 else "warning"


# Dose V4.1 §2.5 (Sean D2, 2026-10-17): catalog safety screening uses the
# lowest established UL across the product's whole population. With no stated
# population that is every ordinary adult group; a stated population narrows
# it. Adequacy keeps its own reference profile. A UL is a total-intake limit:
# a product below it does not establish that food plus supplements stays below.
_ADULT_AGES = ("19-30", "31-50", "51-70", "71+")
UL_SCREENING_POPULATIONS = {
    "general_adult": {"groups": ("Male", "Female"), "ages": _ADULT_AGES, "label": "general adult"},
    "adults_19_50": {"groups": ("Male", "Female"), "ages": ("19-30", "31-50"), "label": "adults 19-50"},
    "adults_51_plus": {"groups": ("Male", "Female"), "ages": ("51-70", "71+"), "label": "adults 51+"},
    # Ordinary adult pregnancy and lactation (19-50); adolescent life stages
    # belong with the pediatric screen below, as for the general adult screen.
    "pregnancy_lactation": {"groups": ("Pregnancy", "Lactation"), "ages": ("19-30", "31-50"),
                            "label": "pregnancy and lactation"},
    # Children screen the NASEM rows for the ages the label states (Sean,
    # 2026-10-19). A stated age without a UL row for this nutrient (infants;
    # vanadium for every child age) never borrows an older limit: it stays an
    # explicit reference gap and the assessment stays incomplete.
    "pediatric": {"groups": ("Male", "Female"), "ages": ("0-1", "1-3", "4-8", "9-13", "14-18"),
                  "label": "children and adolescents",
                  "reference_gap": "pediatric_ul_row_missing_for_stated_age"},
}
# NASEM DRI life-stage bands for children, as [lower, upper) years of age.
PEDIATRIC_AGE_BANDS = (("0-1", 0, 1), ("1-3", 1, 4), ("4-8", 4, 9), ("9-13", 9, 14), ("14-18", 14, 19))
# A pediatric label that states no age covers children 1-18; DSLD files infants separately.
_BROAD_PEDIATRIC_AGES = ("1-3", "4-8", "9-13", "14-18")
_PEDIATRIC_WORDS = ("child", "infant", "boys", "girls")
_AGE_LABELS = {("51-70", "71+"): "adults 51+", ("71+",): "adults 71+", ("51-70",): "adults 51-70",
               ("19-30", "31-50"): "adults 19-50", ("19-30",): "adults 19-30", ("31-50",): "adults 31-50"}

# DSLD target groups that state a narrower population. DSLD files its generic
# adult category ("Adult (18 - 50 Years)" and the male/female variants) on
# most labels (12,102 of 15,426 stored inputs carry it alone), so those tags
# do not narrow the general adult screen.
# Checked in order per tag: a negated life stage ("Women (not pregnant or
# lactating)", 959 stored labels) is an ordinary adult, never that stage.
_UL_POPULATION_TAGS = (
    ("general_adult", ("not pregnant", "not lactating")),
    ("pregnancy_lactation", ("pregnant", "lactating")),
    ("adults_51_plus", ("seniors/mature (>50",)),
    ("pediatric", _PEDIATRIC_WORDS),
    ("general_adult", ("adult (18 - 50", "adult male (18", "adult female (18", "menopause")),
)


def label_population_members(product: Dict) -> Tuple[str, ...]:
    """The existing label-population selection shared by source consumers.

    The UL screen and reference applicability read the same DSLD target groups;
    a label naming several populations retains every member.
    """
    found = set()
    for group in product.get("targetGroups") or []:
        tag = _target_group_text(group)
        population = next((population for population, needles in _UL_POPULATION_TAGS
                           if any(needle in tag for needle in needles)), None)
        # An explicit 19-50 restriction reaches its existing UL owner. The
        # broad DSLD 18-50 category remains general adult. Life-stage tags
        # retain precedence; negated pregnancy/lactation is ordinary adult.
        if population in {None, "general_adult"} and re.search(
            r"(?<![\d-])19\s*[-–—]\s*50(?!\d)", tag
        ):
            population = "adults_19_50"
        if population:
            found.add(population)
    return tuple(sorted(found or {"general_adult"}))


def _target_group_text(group: Any) -> str:
    text = group if isinstance(group, str) else (
        (group.get("text") or group.get("name") or "") if isinstance(group, dict) else "")
    return str(text).strip().lower()


_AGE = r"(\d+(?:\.\d+)?)\s*(months?|years?|yrs?)?"


def _in_years(value: str, unit: Optional[str], default_unit: str) -> float:
    return float(value) / 12 if (unit or default_unit).startswith("month") else float(value)


def _pediatric_years(tag: str) -> Tuple[float, float]:
    """The [lower, upper) years of age one pediatric DSLD target group states.

    Every number keeps its own unit ("6 months to 3 years"); a bare number takes
    the tag's only stated unit. An upper bound stays an upper bound whether it is
    stated in months or years, so "under 12 months" is infants only.
    """
    if "infant" in tag or "baby" in tag:
        return 0, 1
    default = "months" if "month" in tag and not re.search(r"\byears?\b|\byrs?\b", tag) else "years"
    between = re.search(r"more than\s*" + _AGE + r"\s*but less than\s*" + _AGE, tag)
    if between:
        low, low_unit, high, high_unit = between.groups()
        return _in_years(low, low_unit or high_unit, default), _in_years(high, high_unit, default)
    span = re.search(_AGE + r"\s*(?:[-–—]|to)\s*" + _AGE, tag)
    if span:
        low, low_unit, high, high_unit = span.groups()
        unit = high_unit or low_unit or default
        # An inclusive end: "6-36 months" includes month 36, "4-8 years" includes age 8.
        step = 1 / 12 if unit.startswith("month") else 1
        return _in_years(low, low_unit or high_unit, default), _in_years(high, high_unit, default) + step
    at_least = re.search(_AGE + r"\s*(?:or more|\+|and (?:up|older|over))", tag)
    if at_least:
        return _in_years(at_least.group(1), at_least.group(2), default), 19
    under = re.search(r"(?:under|less than|younger than)\s*" + _AGE, tag)
    if under:
        return 0, _in_years(under.group(1), under.group(2), default)
    return 1, 19


def label_pediatric_age_ranges(product: Dict) -> Optional[Tuple[str, ...]]:
    """The NASEM child age bands the label's pediatric target groups cover.

    None when no target group names children. Several pediatric tags cover the
    union of their ages, so the screen takes the lowest limit across all of them.
    """
    covered: set = set()
    pediatric = False
    for group in product.get("targetGroups") or []:
        tag = _target_group_text(group)
        if not (any(word in tag for word in _PEDIATRIC_WORDS)
                or _CHILD_PRODUCT_WORDS.search(_canonical_label_text(tag))):
            continue
        pediatric = True
        low, high = _pediatric_years(tag)
        # A child tag whose ages match no NASEM band cannot be placed: it stays unresolved, so
        # the screen keeps a reference gap instead of reading "no ages" as "no limit".
        covered |= {age for age, band_low, band_high in PEDIATRIC_AGE_BANDS
                    if band_low < high and low < band_high} or {"unresolved"}
    if not pediatric:
        return None
    ordered = tuple(age for age, _, _ in PEDIATRIC_AGE_BANDS if age in covered)
    return ordered + (("unresolved",) if "unresolved" in covered else ())


# A children's product: its title names children, or its target groups name
# children and no adult group. Moved unchanged from the omega Evidence check
# (evidence_resolver), which now calls it, so both consumers share one rule.
_CHILD_PRODUCT_WORDS = re.compile(
    r"\b(?:baby|babies|infant|infants|child|children|kids?|toddler|toddlers|pediatric|junior|jr)\b"
)
_ADULT_TARGET_WORDS = re.compile(
    r"\b(?:adults?|seniors?|mature|men|women|pregnant|lactating|menopause|menopausal)\b"
)


def _canonical_label_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()


def _label_title(product: Mapping, canonical: bool = True) -> str:
    title = " ".join(
        str(product.get(key) or "") for key in ("product_name", "fullName", "brand_name", "brandName")
    )
    # Ages are read from the lowercased title, which keeps "4+" and "1-3".
    return _canonical_label_text(title) if canonical else title.strip().lower()


def label_is_for_children(product: Mapping) -> bool:
    """Whether the label is a children's product.

    ``targetGroups`` describes the intended users (``userGroups`` describes the
    Daily Value population and must not select it). A DSLD child tag beside an
    adult tag does not make an adult product a children's product.
    """
    groups = product.get("targetGroups") or []
    if isinstance(groups, str):
        groups = [groups]
    target = _canonical_label_text(" ".join(
        str(group.get("text") or group.get("name") or "") if isinstance(group, Mapping) else str(group)
        for group in groups
    ))
    return bool(_CHILD_PRODUCT_WORDS.search(_label_title(product))) or (
        bool(_CHILD_PRODUCT_WORDS.search(target)) and not _ADULT_TARGET_WORDS.search(target)
    )


def label_child_ul_ages(product: Mapping) -> Optional[Tuple[str, ...]]:
    """The child ages a children's product's upper-limit notes cover; None otherwise.

    Children are not the scored population (Sean, 2026-10-19): these ages only
    select the child limits shown, accurately, on a children's product. The DSLD
    target groups state the ages; a title-only children's product is read from
    its title, and a title naming no age covers children 1-18.
    """
    if not label_is_for_children(product):
        return None
    ages = label_pediatric_age_ranges(product)
    if ages is None:
        low, high = _pediatric_years(_label_title(product, canonical=False))
        ages = tuple(age for age, band_low, band_high in PEDIATRIC_AGE_BANDS
                     if band_low < high and low < band_high) or ("unresolved",)
    return ages


def _pediatric_age_label(ages: Sequence[str]) -> str:
    """Name the child ages whose limit applies; separate runs are named separately."""
    indexes = [index for index, band in enumerate(PEDIATRIC_AGE_BANDS) if band[0] in ages]
    runs: List[List[int]] = []
    for index in indexes:
        if runs and index == runs[-1][-1] + 1:
            runs[-1].append(index)
        else:
            runs.append([index])
    if PEDIATRIC_AGE_BANDS[indexes[0]][1] >= 14:
        return "adolescents 14-18"
    who = "children" if PEDIATRIC_AGE_BANDS[indexes[-1]][2] - 1 <= 13 else "children and adolescents"
    spans = [f"{PEDIATRIC_AGE_BANDS[run[0]][1]}-{PEDIATRIC_AGE_BANDS[run[-1]][2] - 1}" for run in runs]
    return f"{who} {' and '.join(spans)}"


def ul_source_scope(ul_basis: Optional[str]) -> str:
    """Render the reference owner's source scope without inferring a basis."""
    return {"supplemental_only": " from supplements",
            "total_intake": " from all sources",
            "synthetic_only": " for synthetic forms"}.get(ul_basis, "")


def ul_exceedance_sentence(amount: float, ul: float, unit: str, scope_label: str = "general adult",
                           *, ul_basis: Optional[str] = None,
                           exposure_label: str = "At the assessed daily amount") -> str:
    """Qualify the assessed exposure, population and recorded reference scope."""
    def _n(value: float) -> str:
        return f"{value:.0f}" if abs(value - round(value)) < 0.05 else f"{value:.1f}"

    pct = amount / ul * 100.0 if ul else 0.0
    limit = ("general adult upper limit" if scope_label == "general adult"
             else f"upper limit for {scope_label}")
    return (
        f"{exposure_label}, this product provides {_n(amount)} {unit} per day, "
        f"{pct:.0f}% of the {limit} of {_n(ul)} {unit}{ul_source_scope(ul_basis)}."
    )


@dataclass
class NutrientAdequacyResult:
    """Result of nutrient adequacy calculation."""
    nutrient: str
    amount: float
    unit: str
    rda_ai: Optional[float]
    rda_ai_source: str  # "rda" or "ai" (adequate intake)
    ul: Optional[float]
    ul_status: str  # "established", "not_determined", "not_applicable"
    optimal_min: Optional[float]
    optimal_max: Optional[float]
    pct_rda: Optional[float]
    pct_ul: Optional[float]
    adequacy_band: str
    over_ul: bool
    over_ul_amount: Optional[float]
    scoring_eligible: bool
    point_recommendation: int  # What scoring COULD award
    notes: List[str]
    warnings: List[str]
    age_group: str
    sex_group: str
    # Sprint E1.5.X-5 (2026-05-01): consolidate highest_ul into adequacy_results
    # so both `analyzed_ingredients[]` and `adequacy_results[]` carry the same
    # field. Eliminates the prior split where Flutter's anonymous-user UL
    # fallback only worked via analyzed_ingredients[]. Per dev decision: ONE
    # canonical highest_ul field surfaced wherever the per-nutrient record
    # appears.
    highest_ul: Optional[float] = None
    reference: Optional[Dict] = None
    # Which population's lowest UL screened this exposure (D2); None when the
    # UL came from the single age/sex reference row.
    ul_population: Optional[Dict] = None

    def to_dict(self) -> Dict:
        return {
            "nutrient": self.nutrient,
            "amount": self.amount,
            "unit": self.unit,
            "rda_ai": self.rda_ai,
            "rda_ai_source": self.rda_ai_source,
            "ul": self.ul,
            "ul_status": self.ul_status,
            "optimal_min": self.optimal_min,
            "optimal_max": self.optimal_max,
            "pct_rda": self.pct_rda,
            "pct_ul": self.pct_ul,
            "adequacy_band": self.adequacy_band,
            "over_ul": self.over_ul,
            "over_ul_amount": self.over_ul_amount,
            "scoring_eligible": self.scoring_eligible,
            "point_recommendation": self.point_recommendation,
            "notes": self.notes,
            "warnings": self.warnings,
            "age_group": self.age_group,
            "sex_group": self.sex_group,
            "highest_ul": self.highest_ul,
            "reference": self.reference,
            "ul_population": self.ul_population,
        }


class RDAULCalculator:
    """
    Calculates nutrient adequacy based on RDA/AI and UL values.

    Outputs evidence data for scoring consumption - does NOT compute
    final scores (that's the scorer's job).
    """

    # Formal FNB reference types for the life stages this calculator supports
    # (14 years and older). Other registry values are authored dose anchors,
    # not government RDAs or AIs. This labels provenance; it does not calibrate
    # the scorer's separate DRI/clinical-anchor credit policy.
    _AI_NUTRIENT_IDS = frozenset({
        "vitamin_k", "biotin", "pantothenic_acid", "choline", "chromium",
        "manganese", "potassium", "sodium", "chloride", "fluoride",
        "alpha_linolenic_acid",
    })
    _RDA_NUTRIENT_IDS = frozenset({
        "vitamin_a", "vitamin_c", "vitamin_d", "vitamin_e", "thiamin",
        "riboflavin", "niacin", "vitamin_b6", "folate", "vitamin_b12",
        "calcium", "magnesium", "iron", "zinc", "copper", "selenium",
        "iodine", "molybdenum", "phosphorus",
    })

    # Age group normalization
    AGE_NORMALIZATION = {
        "14-18": "14-18",
        "19-30": "19-30",
        "31-50": "31-50",
        "51-70": "51-70",
        "71+": "71+",
        "adult": "19-30",  # Default adult
        "default": "19-30"
    }

    # Sex group normalization
    SEX_NORMALIZATION = {
        "male": "Male",
        "m": "Male",
        "female": "Female",
        "f": "Female",
        "pregnancy": "Pregnancy",
        "pregnant": "Pregnancy",
        "lactation": "Lactation",
        "lactating": "Lactation",
        "both": "Male",  # Use male as default when both
        "adult_neutral": "Adult neutral",
        "default": "Male"
    }

    def __init__(self, rda_db_path: Optional[Path] = None):
        """
        Initialize the calculator.

        Args:
            rda_db_path: Path to rda_optimal_uls.json.
                        If None, uses default location.
        """
        if rda_db_path is None:
            rda_db_path = Path(__file__).parent / "data" / "rda_optimal_uls.json"

        self.rda_db = self._load_rda_db(rda_db_path)
        self._build_nutrient_lookup()

    def _load_rda_db(self, path: Path) -> Dict:
        """Load the RDA/UL database. Raises on failure — UL safety checks depend on this."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            raise RuntimeError(
                f"FATAL: Failed to load RDA/UL database from {path}: {e}. "
                f"Upper-limit safety checks cannot run without this file."
            ) from e
        if not data.get("nutrient_recommendations"):
            raise ValueError(
                f"RDA database at {path} has no nutrient_recommendations — "
                f"UL violation detection will be completely disabled."
            )
        return data

    def _build_nutrient_lookup(self):
        """Build fast lookup for nutrients by name."""
        self.nutrient_lookup = {}
        self.nutrient_aliases = {}

        for nutrient in self.rda_db.get("nutrient_recommendations", []):
            std_name = nutrient.get("standard_name", "")
            nutrient_id = nutrient.get("id", "")

            # Index by standard name
            key = self._normalize_nutrient_name(std_name)
            self.nutrient_lookup[key] = nutrient

            # Index by id
            if nutrient_id:
                self.nutrient_lookup[nutrient_id.lower()] = nutrient

            # Add common aliases
            aliases = nutrient.get("aliases", [])
            for alias in aliases:
                alias_key = self._normalize_nutrient_name(alias)
                self.nutrient_aliases[alias_key] = key

    def _normalize_nutrient_name(self, name: str) -> str:
        """Normalize nutrient name for lookup."""
        if not name:
            return ""
        # Lowercase, remove special chars, normalize spaces
        normalized = name.lower()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', '_', normalized.strip())
        return normalized

    @staticmethod
    def _canonical_mass_unit(unit: Optional[str]) -> Optional[str]:
        """Return 'g' | 'mg' | 'mcg' for a mass unit, else None.

        Handles qualified reference units like 'mcg RAE' / 'mcg DFE' by taking
        the leading token, and the µg/ug spellings of micrograms.
        """
        if not unit:
            return None
        s = str(unit).strip().lower()
        parts = s.split()
        token = parts[0] if parts else s
        canonical = canonicalize_mass_unit(token)
        return canonical if canonical in _MASS_TO_MCG else None

    @staticmethod
    def _reconcile_amount_to_reference(
        amount: float,
        from_unit: Optional[str],
        ref_unit: Optional[str],
    ) -> Tuple[Optional[float], bool]:
        """Express ``amount`` (in ``from_unit``) in the table's ``ref_unit``.

        Returns ``(amount_in_ref_unit, evaluable)``. ``evaluable`` is False when
        the units are not comparable (e.g. raw IU vs a mass reference); callers
        MUST NOT compute pct_rda/pct_ul in that case — "not evaluable", never a
        false flag. A missing ``ref_unit`` preserves the historical assumption
        that ``amount`` is already in the reference unit.
        """
        if not ref_unit:
            return amount, True
        fu = RDAULCalculator._canonical_mass_unit(from_unit)
        ru = RDAULCalculator._canonical_mass_unit(ref_unit)
        if fu is not None and ru is not None:
            return amount * (_MASS_TO_MCG[fu] / _MASS_TO_MCG[ru]), True
        # Identical raw unit strings (e.g. both 'IU') are comparable as-is.
        if str(from_unit or "").strip().lower() == str(ref_unit or "").strip().lower():
            return amount, True
        # One side is non-mass (IU, %, …) and they differ: cannot compare.
        return None, False

    def compute_nutrient_adequacy(
        self,
        nutrient: str,
        amount: float,
        unit: str,
        age_group: str = "19-30",
        sex: str = "both",
        form_name: Optional[str] = None,
        ul_population: Optional[Union[str, Sequence[str]]] = None,
        pediatric_age_groups: Optional[Sequence[str]] = None,
    ) -> NutrientAdequacyResult:
        """
        Compute nutrient adequacy with full evidence.

        Args:
            nutrient: Nutrient name (will be normalized)
            amount: Amount per serving (already unit-converted)
            unit: Unit of amount
            age_group: Age range (e.g., "19-30", "51-70")
            sex: "male", "female", or "both"
            ul_population: ``UL_SCREENING_POPULATIONS`` key(s); when given, the UL
                is the lowest established UL across every listed population (D2)

        Returns:
            NutrientAdequacyResult with all evidence
        """
        notes = []
        warnings = []

        # Normalize inputs
        norm_age = self.AGE_NORMALIZATION.get(age_group, self.AGE_NORMALIZATION["default"])
        norm_sex = self.SEX_NORMALIZATION.get(sex.lower() if sex else "both", self.SEX_NORMALIZATION["default"])

        # Find nutrient data
        nutrient_data = self._find_nutrient(nutrient, form_name=form_name)

        if not nutrient_data:
            return NutrientAdequacyResult(
                nutrient=nutrient,
                amount=amount,
                unit=unit,
                rda_ai=None,
                rda_ai_source="unknown",
                ul=None,
                ul_status="unknown",
                optimal_min=None,
                optimal_max=None,
                pct_rda=None,
                pct_ul=None,
                adequacy_band="unknown",
                over_ul=False,
                over_ul_amount=None,
                scoring_eligible=False,
                point_recommendation=0,
                notes=[f"Nutrient '{nutrient}' not found in RDA database"],
                warnings=[],
                age_group=norm_age,
                sex_group=norm_sex
            )

        # Get age/sex specific values
        rda_ai, ul = self._get_age_sex_values(nutrient_data, norm_age, norm_sex)
        population = None
        if ul_population is not None:
            ul, population = self._screening_ul(nutrient_data, ul_population, pediatric_age_groups)

        # Determine RDA source
        nutrient_id = nutrient_data.get("id")
        rda_source = (
            "ai" if nutrient_id in self._AI_NUTRIENT_IDS else
            "rda" if nutrient_id in self._RDA_NUTRIENT_IDS else "unknown"
        )
        if rda_ai is None:
            # Check for AI value
            ai_data = self._get_ai_value(nutrient_data, norm_age, norm_sex)
            if ai_data:
                rda_ai = ai_data
                # The shared numeric field alone cannot establish provenance.

        # Check UL status
        ul_status = self._determine_ul_status(nutrient_data, ul, norm_age, norm_sex)

        # NASEM's nickel upper reference covers soluble nickel salts. A
        # nutrient declaration proves elemental mass, not salt solubility.
        if nutrient_id == "nickel":
            allowed = {self._normalize_nutrient_name(value)
                       for value in nutrient_data.get("ul_applies_to_forms") or []}
            if self._normalize_nutrient_name(form_name or nutrient) not in allowed:
                ul_status = "indeterminate"
                notes.append("Nickel UL not evaluated: soluble salt identity is unresolved.")
            warnings.append(nutrient_data.get("ul_note") or "")

        # Get optimal range
        optimal_min, optimal_max = self._parse_optimal_range(nutrient_data.get("optimal_range", ""))

        # Reconcile the label amount to the RDA/UL table's own unit BEFORE any
        # percentage math. unit_converter.convert_nutrient is a no-op for plain
        # minerals, so `amount`/`unit` can still be in the label unit (e.g. mcg)
        # while rda_ai/ul are in the table unit (e.g. mg). Comparing them raw
        # produced false over-UL flags (Boron 150 mcg vs a 20 mg UL -> 750%) and
        # missed exposures (Copper 2 mg read as 0.22% of a 900 mcg RDA).
        reference_unit = nutrient_data.get("unit")
        amount_in_ref, unit_evaluable = self._reconcile_amount_to_reference(
            amount, unit, reference_unit
        )
        ref_unit_label = reference_unit or unit

        # Calculate percentages
        pct_rda = None
        pct_ul = None
        over_ul = False
        over_ul_amount = None

        if not unit_evaluable:
            # Units are not comparable (e.g. raw IU vs a mass reference). Do NOT
            # fabricate a percentage — leave adequacy/UL unevaluated.
            notes.append(
                f"UL/RDA not evaluated: label unit '{unit}' is not comparable to "
                f"the reference unit '{reference_unit}' (needs form-aware conversion)."
            )
        else:
            if rda_ai and rda_ai > 0:
                pct_rda = (amount_in_ref / rda_ai) * 100
                reference_name = {"rda": "RDA", "ai": "AI"}.get(rda_source, "authored dose reference")
                notes.append(f"{pct_rda:.1f}% of {reference_name} ({rda_ai} {ref_unit_label})")

            if ul and ul > 0 and ul_status == "established":
                pct_ul = (amount_in_ref / ul) * 100
                if amount_in_ref > ul:
                    over_ul = True
                    over_ul_amount = amount_in_ref - ul
                    warnings.append(ul_exceedance_sentence(
                        amount_in_ref, ul, ref_unit_label,
                        (population or {}).get("label") or "general adult",
                        ul_basis=nutrient_data.get("ul_basis")))

        # Determine adequacy band. Magnesium is a special case because the UL
        # applies to supplemental intake only while the RDA is total intake.
        uses_supplement_only_ul = self._uses_supplement_only_ul_policy(nutrient_data)
        if over_ul and uses_supplement_only_ul:
            notes.append("Supplemental magnesium has a separate UL from the total-intake RDA.")
            warnings.append(
                f"Supplemental magnesium exceeds the adult supplemental UL by {over_ul_amount:.1f} {ref_unit_label}"
            )
        adequacy_band = self._determine_adequacy_band(
            pct_rda,
            over_ul and not uses_supplement_only_ul
        )

        # Handle "no UL" policy
        if ul_status == "not_determined":
            notes.append("No UL established for this nutrient")
            if nutrient_data.get("id") == "vanadium" and nutrient_data.get("ul_note"):
                warnings.append(nutrient_data["ul_note"])
            if adequacy_band == "excessive":
                # Do not turn an RDA multiple into a toxicity proxy when the
                # authoritative reference has no UL. Retain reduced high-dose
                # adequacy credit without implying that the exposure is safe.
                adequacy_band = "high"
                notes.append(
                    "Adequacy band capped at high because no UL is established; "
                    "this is not a safety conclusion."
                )
            # Flag extreme doses (>10x RDA) for information only
            if pct_rda and pct_rda > 1000:
                notes.append(f"Note: Amount is {pct_rda/100:.1f}x reference intake (informational only, no UL applies)")

        # Get point recommendation from band
        point_recommendation = ADEQUACY_BANDS.get(adequacy_band, {}).get("points", 0)

        # Determine scoring eligibility
        scoring_eligible = True
        if pct_rda is None:
            scoring_eligible = False
            notes.append("No RDA/AI found - not scored")
        elif (
            rda_source == "unknown"
            and (nutrient_data.get("reference_semantics") or {}).get("curve")
            == "completed_no_benchmark_neutral"
        ):
            # Retained study amounts are descriptive, not nutritional targets.
            # All panel consumers read this eligibility result; official RDA/AI
            # rows (including dietary sodium/potassium) keep their own policy.
            scoring_eligible = False
            notes.append("Completed review: no general nutritional benchmark; excluded from nutritional Dose coverage.")
        elif adequacy_band == "excessive" or over_ul:
            # Still eligible but points may be 0 or negative
            pass

        # Sprint E1.5.X-5 (2026-05-01): pull highest_ul from the RDA file so
        # adequacy_results[].highest_ul matches analyzed_ingredients[].highest_ul.
        # Coerced to float when stored as string.
        _highest_ul_raw = nutrient_data.get("highest_ul")
        if isinstance(_highest_ul_raw, str):
            try:
                _highest_ul_raw = float(_highest_ul_raw)
            except (TypeError, ValueError):
                _highest_ul_raw = None
        elif _highest_ul_raw is not None and not isinstance(_highest_ul_raw, (int, float)):
            _highest_ul_raw = None

        reference_url = ((self.rda_db.get("consumer_ul_warnings", {}).get(nutrient_data.get("id"), {}) or {}).get("source_url")
                         or nutrient_data.get("ul_scope_source"))
        authoritative_ul = isinstance(reference_url, str) and reference_url.startswith(("https://ods.od.nih.gov/factsheets/", "https://www.nationalacademies.org/read/")) and ul_status == "established"
        return NutrientAdequacyResult(
            nutrient=nutrient,
            amount=amount,
            unit=unit,
            rda_ai=rda_ai,
            rda_ai_source=rda_source,
            ul=ul if ul_status == "established" else None,
            ul_status=ul_status,
            optimal_min=optimal_min,
            optimal_max=optimal_max,
            pct_rda=pct_rda,
            pct_ul=pct_ul,
            adequacy_band=adequacy_band,
            over_ul=over_ul,
            over_ul_amount=over_ul_amount,
            scoring_eligible=scoring_eligible,
            point_recommendation=point_recommendation,
            notes=notes,
            warnings=warnings,
            age_group=norm_age,
            sex_group=norm_sex,
            highest_ul=_highest_ul_raw,
            reference={
                "source_owner": "rda_ul_data",
                "source_url": reference_url,
                "basis_type": "authoritative_safety_reference" if authoritative_ul else "catalog_reference",
                "evidence_grade_applicable": False if authoritative_ul else None,
                "ul_basis": nutrient_data.get("ul_basis"),
                "ul_note": nutrient_data.get("ul_note"),
            },
            ul_population=population,
        )

    def _lookup_key(self, key: str) -> Optional[Dict]:
        if key in self.nutrient_lookup:
            return self.nutrient_lookup[key]
        if key in self.nutrient_aliases:
            return self.nutrient_lookup.get(self.nutrient_aliases[key])
        return None

    def _form_scoped_reference(self, record: Optional[Dict], form_name: Optional[str]) -> Optional[Dict]:
        """IQM parent membership does not prove equivalence to a trial material.

        Keep the registered forms/parents intact; abstain from the parent's
        reference when a different chemical preparation has no own anchor.
        These are reference exclusions, not new amounts or ingredient aliases.
        """
        excluded = {
            "betaine_tmg": {"betaine hydrochloride", "betaine hcl"},
            "l_glutamine": {"n-acetyl-l-glutamine", "l-alanyl-l-glutamine"},
            # ALCAR is an acetylated preparation, not the parent's L-carnitine
            # supplemental reference. Its clinical range has a separate owner.
            "l_carnitine": {"acetyl-l-carnitine (alcar)", "acetyl-l-carnitine",
                           "acetyl-l-carnitine hydrochloride"},
            # The anchor's PMID 30566740 reviews sulfate, not HCl or NAG.
            "glucosamine_sulfate": {"glucosamine hydrochloride", "glucosamine hcl",
                                    "n-acetyl glucosamine (NAG)"},
        }
        form = self._normalize_nutrient_name(form_name or "")
        if record and form in {self._normalize_nutrient_name(value)
                               for value in excluded.get(record.get("id"), set())}:
            return None
        return record

    def _find_nutrient(self, name: str, *, form_name: Optional[str] = None) -> Optional[Dict]:
        """Find a nutrient by exact standard name, id or alias.

        A numbered vitamer names its vitamin (Vitamin D3 -> Vitamin D). A label
        name such as "Vitamin B9 (Folate)" may name the compound outside or
        inside its parentheses, so each part is also looked up exactly; parts
        naming two different references resolve to neither. There is no
        substring matching: "TMG (Trimethylglycine)" contains "glycine" and
        "Echinacea" contains "nac", but neither is that compound.
        """
        key = self._normalize_nutrient_name(name)
        form_name = form_name or name
        direct = self._lookup_key(key)
        if direct:
            return self._form_scoped_reference(direct, form_name)
        vitamer = re.fullmatch(r"(vitamin_[a-z])\d+", key)
        if vitamer and self._lookup_key(vitamer.group(1)):
            return self._form_scoped_reference(self._lookup_key(vitamer.group(1)), form_name)
        parts = re.fullmatch(r"\s*(.+?)\s*\((.+)\)\s*", name or "")
        if not parts:
            return None
        hits = {}
        for part in parts.groups():
            hit = self._lookup_key(self._normalize_nutrient_name(part))
            if hit:
                hits[id(hit)] = hit
        return self._form_scoped_reference(next(iter(hits.values())), form_name) if len(hits) == 1 else None

    def _get_age_sex_values(
        self,
        nutrient_data: Dict,
        age_group: str,
        sex: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """Get RDA/AI and UL for specific age/sex group."""
        data_list = nutrient_data.get("data", [])

        if sex == "Adult neutral":
            adult_rows = [
                entry
                for entry in data_list
                if entry.get("group") in {"Male", "Female"}
                and entry.get("age_range") == age_group
            ]
            rda_values = [
                entry.get("rda_ai")
                for entry in adult_rows
                if isinstance(entry.get("rda_ai"), (int, float))
            ]
            ul_values = [
                entry.get("ul")
                for entry in adult_rows
                if isinstance(entry.get("ul"), (int, float))
            ]
            if adult_rows:
                # Compatibility profile: adequacy must satisfy the higher
                # sourced adult reference; safety uses the lower sourced UL.
                return (
                    max(rda_values) if rda_values else None,
                    min(ul_values) if ul_values else None,
                )

        for entry in data_list:
            if entry.get("group") == sex and entry.get("age_range") == age_group:
                rda = entry.get("rda_ai")
                ul = entry.get("ul")

                # UL and RDA are now numeric or null (no more "ND" strings)
                if not isinstance(ul, (int, float)):
                    ul = None
                if not isinstance(rda, (int, float)):
                    rda = None

                return rda, ul

        # Fallback to highest_ul if specific value not found
        fallback_ul = nutrient_data.get("highest_ul")
        if isinstance(fallback_ul, str):
            try:
                fallback_ul = float(fallback_ul)
            except ValueError:
                fallback_ul = None
        return None, fallback_ul

    def _screening_ul(self, nutrient_data: Dict, population: Union[str, Sequence[str]],
                      pediatric_age_groups: Optional[Sequence[str]] = None) -> Tuple[Optional[float], Dict]:
        """Lowest established UL across every listed screening population, and its scope."""
        members = sorted({population} if isinstance(population, str) else set(population))
        pediatric_ages = (tuple(pediatric_age_groups) if pediatric_age_groups is not None
                          else _BROAD_PEDIATRIC_AGES) or ("unresolved",)
        rows_by_member = {member: [
            row for row in nutrient_data.get("data", [])
            if row.get("group") in UL_SCREENING_POPULATIONS[member]["groups"]
            and row.get("age_range") in UL_SCREENING_POPULATIONS[member]["ages"]
            and (member != "pediatric" or row.get("age_range") in pediatric_ages)
            and isinstance(row.get("ul"), (int, float)) and not isinstance(row.get("ul"), bool)
            and row.get("ul") > 0] for member in members}
        scope = {"id": "+".join(members), "members": members,
                 "label": " and ".join(dict.fromkeys(UL_SCREENING_POPULATIONS[m]["label"] for m in members))}
        # Every stated child age needs its own row. A missing age row is a gap
        # only for an established upper reference: completed "no established
        # UL" records (for example B12) retain that conclusion.
        missing_ages = [age for age in pediatric_ages if "pediatric" in members
                        and not any(row["age_range"] == age for row in rows_by_member["pediatric"])]
        if missing_ages and any(
            isinstance(row.get("ul"), (int, float)) and not isinstance(row.get("ul"), bool)
            and row["ul"] > 0 and self._determine_ul_status(nutrient_data, row["ul"]) == "established"
            for row in nutrient_data.get("data", [])
        ):
            scope["reference_gap"] = UL_SCREENING_POPULATIONS["pediatric"]["reference_gap"]
            scope["missing_age_ranges"] = missing_ages
        all_rows = [row for rows in rows_by_member.values() for row in rows]
        if not all_rows:
            if "pediatric" in members:
                scope["label"] = "pediatric"
            return None, scope
        ul = min(row["ul"] for row in all_rows)
        labels, ages = [], []
        for member, rows in rows_by_member.items():
            spec = UL_SCREENING_POPULATIONS[member]
            member_ages = tuple(age for age in spec["ages"] if any(
                row["age_range"] == age and row["ul"] == ul for row in rows))
            if not member_ages:
                continue
            label = spec["label"]
            if member == "general_adult" and len({row["ul"] for row in rows}) > 1:
                label = _AGE_LABELS.get(member_ages, label)
            elif member == "pediatric":
                label = _pediatric_age_label(member_ages)
            labels.append(label)
            ages.extend(age for age in member_ages if age not in ages)
        scope["label"] = " and ".join(dict.fromkeys(labels))
        scope["age_ranges"] = ages
        return ul, scope

    def _get_ai_value(
        self,
        nutrient_data: Dict,
        age_group: str,
        sex: str
    ) -> Optional[float]:
        """Get AI (Adequate Intake) if RDA not available."""
        # Check if this nutrient uses AI instead of RDA
        data_list = nutrient_data.get("data", [])

        for entry in data_list:
            if entry.get("group") == sex and entry.get("age_range") == age_group:
                ai_value = entry.get("rda_ai")  # AI is stored in same field
                if ai_value is None:
                    return None
                if isinstance(ai_value, (int, float)):
                    return float(ai_value)
                if isinstance(ai_value, str):
                    try:
                        return float(ai_value)
                    except ValueError:
                        return None
                return None

        return None

    def _determine_ul_status(
        self, nutrient_data: Dict, ul: Optional[float],
        age_group: Optional[str] = None, sex: Optional[str] = None,
    ) -> str:
        """Determine UL status."""
        # Check ul_status field. Floor nutrients carry the granular display schema
        # (not_established_low_toxicity / not_established_insufficient_data) or the
        # legacy "not_determined" — all mean "no enforceable UL" to the calculator.
        # Map them to the internal "not_determined" so a soft toxicity-study
        # highest_ul (e.g. vanadium's 1800) is never treated as an established UL.
        nutrient_class = nutrient_data.get("nutrient_class")
        ul_status = nutrient_data.get("ul_status")
        if nutrient_class == "floor" or ul_status in (
            "not_determined",
            "not_established_low_toxicity",
            "not_established_insufficient_data",
        ):
            return "not_determined"

        if ul is not None and ul > 0:
            return "established"

        # An adult ceiling does not establish a ceiling for a life stage whose
        # native row explicitly records insufficient data.
        matching_rows = [
            row for row in nutrient_data.get("data", [])
            if row.get("age_range") == age_group
            and (row.get("group") == sex or
                 (sex == "Adult neutral" and row.get("group") in {"Male", "Female"}))
        ]
        if any(row.get("ul_status") == "not_determined" for row in matching_rows):
            return "not_determined"

        # Check highest_ul
        highest = nutrient_data.get("highest_ul")
        if highest is None:
            return "not_determined"

        return "not_applicable"

    def _parse_optimal_range(self, range_str: str) -> Tuple[Optional[float], Optional[float]]:
        """Parse optimal range string like '200-2000'."""
        if not range_str:
            return None, None

        match = re.match(r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)', str(range_str))
        if match:
            return float(match.group(1)), float(match.group(2))

        return None, None

    def _uses_supplement_only_ul_policy(self, nutrient_data: Dict) -> bool:
        """Return True for nutrients whose over-UL exceedance is treated as benign.

        Magnesium-only by design: its supplemental UL (350 mg) is a GI-tolerance
        threshold well below toxicity, so exceeding it is informational, not a
        scoring penalty. This is intentionally NOT driven by the data's
        ``ul_basis`` field — niacin/folate/vitamin_e also carry supplemental/
        synthetic ``ul_basis`` (the UL is measured on supplemental intake), but
        their ULs are real safety limits whose exceedance must still penalize.
        """
        return nutrient_data.get("id") == "magnesium"

    def _determine_adequacy_band(
        self,
        pct_rda: Optional[float],
        over_ul: bool
    ) -> str:
        """Determine adequacy band based on percentage of RDA."""
        if pct_rda is None:
            return "unknown"

        if over_ul:
            return "excessive"

        for band_name, band_info in ADEQUACY_BANDS.items():
            if band_info["min_pct"] <= pct_rda < band_info["max_pct"]:
                return band_name

        return "unknown"


# Convenience functions
def compute_nutrient_adequacy(
    nutrient: str,
    amount: float,
    unit: str,
    age_group: str = "19-30",
    sex: str = "both",
    rda_db_path: Optional[Path] = None
) -> Dict:
    """
    Convenience function to compute nutrient adequacy.

    Returns dictionary suitable for adding to enriched product data.
    """
    calculator = RDAULCalculator(rda_db_path)
    result = calculator.compute_nutrient_adequacy(nutrient, amount, unit, age_group, sex)
    return result.to_dict()

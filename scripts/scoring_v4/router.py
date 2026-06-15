"""v4 class router — decides which module scores a product.

Priority order (post-taxonomy refactor, 2026-05-20):

  1. probiotic              → probiotic
     - probiotic_data has product-level CFU + named strain identity
     - OR probiotic_data has named strain identity + explicit probiotic name
  2. prenatal multi intent  → multi_or_prenatal
     - product-label prenatal wording plus a true multi/B-complex taxonomy
       or broad prenatal micronutrient panel. Does NOT override probiotic,
       single-purpose prenatal DHA, or single-ingredient products that merely
       live in a prenatal bundle/program.
  3. multivitamin / b-complex → multi_or_prenatal
     - taxonomy primary_type in {multivitamin, b_complex}
     - OR legacy type=multivitamin only when the physical panel is broad
       enough to be a true themed multivitamin
  4. sports                 → sports
     - sports-protein identity (not protein taxonomy alone)
     - OR sports-active canonical panel + explicit sports label intent
     - OR native sports_primary_dose evidence
  5. omega_3                → omega
     - taxonomy primary_type == "omega_3"
     - OR EPA/DHA canonical in ingredient panel (positive quantity)
  6. fall through           → generic

The taxonomy primary_type field comes from scripts/supplement_taxonomy.py
(introduced 2026-05-20) and uses canonical-ID-based panel composition
analysis. It replaces the legacy supp_type heuristic which over-classified
single-issue targeted products (Collagen Love, Mighty Night sleep aid,
Vitafusion Omega-3 EPA/DHA, etc.) as multivitamin. The router prefers
taxonomy and scoring input contracts; the only legacy read is the guarded
themed-multivitamin fallback, which requires a broad disclosed panel.

§13 architecture lock — this router does not import from score_supplements.py.

Omega routing was previously deferred to `generic` per the §9 P1.5
decision gate. P1.6 graduated omega to its own module. P3 added
multi_or_prenatal. This file is the only place where module dispatch
is decided.
"""

from __future__ import annotations

import re
from typing import Any, Dict

from scoring_input_contract import build_scoring_classification, get_scoring_ingredients

VALID_CLASSES = ("generic", "probiotic", "multi_or_prenatal", "omega", "sports")

_PRENATAL_KEYWORDS = re.compile(
    r"\b(prenatal|pregnancy|pre-natal|expecting|maternal|gestation)\b",
    re.IGNORECASE,
)
_PROBIOTIC_NAME_RE = re.compile(
    r"\b(probiotic|probiotics|synbiotic|synbiotics|acidophilus|lactobacillus|"
    r"bifidobacterium|saccharomyces|bacillus)\b",
    re.IGNORECASE,
)
# A probiotic with only a tiny non-probiotic panel (e.g. a probiotic gummy with 1-2
# vitamin adjuncts) can still be probiotic-primary when the name says so. Above this,
# a non-probiotic panel means the strain is an adjunct, not the product's identity.
_PROBIOTIC_ADJUNCT_PANEL_MAX = 2
_PROBIOTIC_HIGH_CFU_BILLIONS = 1.0
# A product whose ONLY scorable identity is >= this many named strains is a
# probiotic even without CFU disclosure or a "probiotic" name token (e.g.
# FLORASSIST: 10 strains, no CFU, brand name lacks "probiotic"). Requires panel==0
# so it cannot capture a vitamin/mineral/protein that merely carries adjunct strains.
_PROBIOTIC_PURE_STRAIN_MIN = 2
_MULTIVITAMIN_BROAD_PANEL_MIN = 8
# The pure-strain promotion (panel==0) is the weakest probiotic signal, so it is
# blocked when the product clearly advertises a NON-probiotic hero. This guards
# against future cleaner/enricher panel-loss turning a zinc/protein/fiber product
# into a "probiotic" just because its real panel was dropped. A vague taxonomy
# (general_supplement) plus no hero keyword is the genuine pure-probiotic case.
_PROBIOTIC_VAGUE_TAXONOMY = frozenset({"", "general_supplement", "probiotic"})
_NON_PROBIOTIC_HERO_TITLE_RE = re.compile(
    r"\b(zinc|magnesium|calcium|iron|potassium|selenium|copper|chromium|iodine|"
    r"vitamin|biotin|folate|folic|niacin|thiamine|riboflavin|"
    r"d2|d3|k2|b12|"
    r"protein|whey|casein|collagen|gelatin|"
    r"enzyme|enzymes|"
    r"fiber|fibre|prebiotic|psyllium|inulin|"
    r"omega|fish\s*oil|krill|cod\s*liver|epa|dha|"
    r"quercetin|curcumin|turmeric|creatine|coq10|ubiquinol|melatonin|ashwagandha)\b",
    re.IGNORECASE,
)
_SPORTS_PREWORKOUT_RE = re.compile(r"\b(pre[\s-]?workout|preworkout)\b", re.IGNORECASE)
_SPORTS_PROTEIN_NAME_RE = re.compile(
    r"\b("
    r"whey|casein|"
    r"protein\s+(?:powder|isolate|concentrate|hydrolysate|hydrolyzed|blend|matrix)|"
    r"mass\s+gainer|gainer"
    r")\b",
    re.IGNORECASE,
)
_SPORTS_TRUE_PROTEIN_NAME_RE = re.compile(
    r"\b(whey|casein|pea\s+protein|rice\s+protein|soy\s+protein|plant(?:-based)?\s+protein|"
    r"protein\s+(?:powder|isolate|concentrate|hydrolysate|hydrolyzed|blend|matrix)|"
    r"mass\s+gainer|gainer)\b",
    re.IGNORECASE,
)
_COLLAGEN_TITLE_RE = re.compile(r"\b(collagen|gelatin|hyaluronic)\b", re.IGNORECASE)
_SPORTS_SINGLE_ACTIVE_NAME_RE = re.compile(
    r"\b(creatine|beta[\s-]?alanine|citrulline|hmb|bcaa|eaa|essential amino|branched chain)\b",
    re.IGNORECASE,
)
_SPORTS_NAME_EXCLUSION_RE = re.compile(
    r"\b(nac|n-acetyl|theanine|tryptophan|5-htp|sam-e|sleep|calm|mood|stress|"
    r"digestive|enzyme|enzymes|keratin|lactoferrin|collagen)\b",
    re.IGNORECASE,
)

# Per scripts/data/omega_rubric.json router.name_keywords. Lowercased
# substring matches against the joined product/brand/bundle name text.
# These are unambiguous multi-character tokens that don't false-positive
# on unrelated products. Short standalone tokens (EPA / DHA) need
# word-boundary regex below to avoid matching inside DHEA / similar.
_OMEGA_NAME_KEYWORDS = (
    "fish oil",
    "omega-3",
    "omega 3",
    "omega3",
    "krill",
    "algae oil",
    "algal oil",
    "cod liver",
    "epa+dha",
    "epa dha",
    "epa/dha",
)
_OMEGA_STRONG_OIL_NAME_KEYWORDS = (
    "fish oil",
    "krill",
    "algae oil",
    "algal oil",
    "cod liver",
    "epa+dha",
    "epa dha",
    "epa/dha",
)

# Standalone EPA / DHA word-boundary detection. CRITICAL: must use \b so
# DHEA (dehydroepiandrosterone) does not match — DHEA is one word, and
# `\bDHA\b` requires DHA to be surrounded by non-word characters. Same
# guard for `\bEPA\b` against any future EPA-prefix false-positives.
# Case-insensitive so labels like "Pure epa" still route.
_OMEGA_STANDALONE_RE = re.compile(r"\b(EPA|DHA)\b", re.IGNORECASE)
_OMEGA_369_RE = re.compile(r"\bomega[\s-]*3[\s-]*[-/]?[\s-]*6[\s-]*[-/]?[\s-]*9\b", re.IGNORECASE)
_OMEGA_EFA_RE = re.compile(r"\bEFA(?:s)?\b", re.IGNORECASE)

# Per scripts/data/omega_rubric.json router.ingredient_panel_canonicals.
# Strong omega signal — operates on the enricher's canonicalized identity
# rather than label text. It is not enough by itself when EPA/DHA is only an
# incidental row in a broad mixed formula; see _has_primary_omega_panel().
_OMEGA_INGREDIENT_CANONICALS = {"epa", "dha", "epa_dha"}
_B_VITAMIN_CANONICALS = {
    "vitamin_b1_thiamine",
    "vitamin_b2_riboflavin",
    "vitamin_b3_niacin",
    "vitamin_b5_pantothenic_acid",
    "vitamin_b5_pantothenic",
    "vitamin_b6_pyridoxine",
    "vitamin_b7_biotin",
    "vitamin_b9_folate",
    "vitamin_b12_cobalamin",
}
_MULTI_PANEL_CANONICALS = _B_VITAMIN_CANONICALS | {
    "vitamin_a",
    "vitamin_c",
    "vitamin_d",
    "vitamin_e",
    "vitamin_k",
    "vitamin_k1",
    "vitamin_k2",
    "folate",
    "iron",
    "iodine",
    "choline",
    "zinc",
    "magnesium",
    "calcium",
    "selenium",
    "manganese",
    "copper",
    "chromium",
    "molybdenum",
}
_NON_B_VITAMIN_CANONICALS = {
    "vitamin_a",
    "vitamin_c",
    "vitamin_d",
    "vitamin_e",
    "vitamin_k",
    "vitamin_k1",
    "vitamin_k2",
}
_MINERAL_CANONICALS = {
    "iron",
    "iodine",
    "zinc",
    "magnesium",
    "calcium",
    "selenium",
    "manganese",
    "copper",
    "chromium",
    "molybdenum",
}
_MULTI_SUPPORT_CANONICALS = {"choline", "folate"}
_LEGACY_MULTIVITAMIN_MIN_MULTI_NUTRIENTS = 5
_PRENATAL_PANEL_ANCHORS = {"folate", "vitamin_b9_folate", "iron", "iodine", "choline", "dha", "epa_dha"}
_NON_EPA_DHA_FATTY_ACID_CANONICALS = {
    "ala", "alpha_linolenic_acid", "alpha_linolenic_acid_ala",
    "omega_3_fatty_acids", "gla", "gamma_linolenic_acid",
    "cla", "conjugated_linoleic_acid", "oleic_acid",
}
_OMEGA_PARENT_CANONICALS = {"fish_oil", "krill_oil", "cod_liver_oil", "algal_oil", "algae_oil", "omega_3"}
_EPA_DHA_SOURCE_RE = re.compile(
    r"\b(epa|dha|eicosapentaenoic|docosahexaenoic)\b",
    re.IGNORECASE,
)
_NON_EPA_DHA_SOURCE_RE = re.compile(
    r"\b("
    r"mct|medium\s+chain\s+triglycerides?|coconut|caprylic|capric|palm|"
    r"flax(?:seed)?|linseed|alpha[-\s]?linolenic|ala|chia|hemp|"
    r"evening\s+primrose|borage|gamma[-\s]?linolenic|gla|"
    r"conjugated\s+linoleic|cla|omega[-\s]?6|omega[-\s]?9|"
    r"fiber|fibre|seed\s+blend|super\s+seed"
    r")\b",
    re.IGNORECASE,
)
_SPORTS_PROTEIN_CANONICALS = {
    "whey_protein",
    "casein",
    "pea_protein",
    "rice_protein",
    "soy_protein",
}
_SPORTS_SINGLE_CANONICALS = {
    "creatine",
    "creatine_monohydrate",
    "creatine_anhydrous",
    "creatine_hydrochloride",
    "creatine_hcl",
    "creatine_nitrate",
    "creatine_citrate",
    "buffered_creatine",
    "magnesium_creatine_chelate",
    "beta-alanine",
    "beta_alanine",
    "l_citrulline",
    "hmb",
}
_BCAA_CANONICALS = {"l_leucine", "l_isoleucine", "l_valine"}
_EAA_CANONICALS = {
    "l_histidine",
    "l_isoleucine",
    "l_leucine",
    "l_lysine",
    "l_methionine",
    "l_phenylalanine",
    "l_threonine",
    "l_tryptophan",
    "l_valine",
}
_EXPLICIT_MULTIVITAMIN_NAME_RE = re.compile(
    r"\b(multivitamin|multi-vitamin|multi vitamin|multimineral)\b",
    re.IGNORECASE,
)


def _scoring_rows(product: Dict[str, Any]) -> list[Dict[str, Any]]:
    return [
        row for row in get_scoring_ingredients(product or {}, strict=True).rows
        if isinstance(row, dict)
    ]


def _positive_quantity(row: Dict[str, Any]) -> bool:
    for key in ("quantity", "amount", "dose", "dosage"):
        value = row.get(key)
        try:
            if value is not None and float(value) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _row_source_text(row: Dict[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in (
            "name",
            "raw_source_text",
            "display_label",
            "normalized_key",
            "parent_key",
            "matched_candidate",
        )
    )


def _source_has_epa_dha_identity(row: Dict[str, Any]) -> bool:
    return bool(_EPA_DHA_SOURCE_RE.search(_row_source_text(row)))


def _source_is_non_epa_dha_oil(row: Dict[str, Any]) -> bool:
    return bool(_NON_EPA_DHA_SOURCE_RE.search(_row_source_text(row)))


def _trustworthy_epa_dha_row(row: Dict[str, Any]) -> bool:
    canonical = str(row.get("canonical_id") or "").strip().lower()
    if canonical not in _OMEGA_INGREDIENT_CANONICALS:
        return False
    if not _positive_quantity(row):
        return False
    if _source_is_non_epa_dha_oil(row) and not _source_has_epa_dha_identity(row):
        return False
    return True


def _omega_panel_counts(product: Dict[str, Any]) -> tuple[int, int]:
    """Return (positive EPA/DHA rows, positive scorable rows).

    The second count is intentionally based on positive scorable rows, not raw
    label rows, so excipients / nested display-only rows do not dilute the
    primary-product check.
    """
    omega_rows = 0
    total_rows = 0
    for ing in _scoring_rows(product):
        if (
            ing.get("scoring_input_kind") == "product_level_evidence"
            and str(ing.get("evidence_type") or "").strip().lower() != "omega_epa_dha_aggregate"
        ):
            continue
        canonical = str(ing.get("canonical_id") or "").strip().lower()
        if not canonical or not _positive_quantity(ing):
            continue
        total_rows += 1
        if canonical in _OMEGA_INGREDIENT_CANONICALS and _trustworthy_epa_dha_row(ing):
            omega_rows += 1
    return omega_rows, total_rows


def _has_primary_omega_panel(product: Dict[str, Any]) -> bool:
    """True when EPA/DHA is the product's primary panel identity.

    Any EPA/DHA row used to route omega. Real-catalog review found mixed
    products with incidental DHA (for example broad antioxidant/amino formulas)
    being forced into the omega module. Require EPA/DHA to be all or at least
    half of positive scorable rows unless explicit omega name intent exists.
    """
    omega_rows, total_rows = _omega_panel_counts(product)
    if omega_rows <= 0 or total_rows <= 0:
        return False
    return omega_rows == total_rows or (omega_rows / total_rows) >= 0.5


def _has_omega_ingredient(product: Dict[str, Any]) -> bool:
    """Return True when EPA/DHA is a primary panel signal, not incidental."""
    return _has_primary_omega_panel(product)


def _has_any_epa_dha_row(product: Dict[str, Any]) -> bool:
    """Return True for any positive EPA/DHA row, even if incidental."""
    for ing in get_scoring_ingredients(product or {}, strict=True).rows:
        if not isinstance(ing, dict):
            continue
        if _trustworthy_epa_dha_row(ing):
            return True
    return False


def _has_omega_scoring_evidence(product: Dict[str, Any]) -> bool:
    for ing in get_scoring_ingredients(product or {}, strict=True).rows:
        if not isinstance(ing, dict):
            continue
        if str(ing.get("evidence_type") or "").strip().lower() == "omega_epa_dha_aggregate":
            return True
    return False


def _has_non_omega_product_level_evidence(product: Dict[str, Any]) -> bool:
    """Return True for conservative product evidence that is not EPA/DHA.

    Name-only omega routing is useful for pure fish-oil labels, but it should
    not pull mixed formulas into the omega module when the scoring contract
    already says the usable evidence is a non-omega blend/header anchor.
    """
    for ing in get_scoring_ingredients(product or {}, strict=True).rows:
        if not isinstance(ing, dict):
            continue
        if ing.get("scoring_input_kind") != "product_level_evidence":
            continue
        evidence_type = str(ing.get("evidence_type") or "").strip().lower()
        canonical = str(ing.get("canonical_id") or "").strip().lower()
        if evidence_type == "omega_epa_dha_aggregate":
            continue
        if canonical in _OMEGA_INGREDIENT_CANONICALS or canonical in _OMEGA_PARENT_CANONICALS:
            continue
        return True
    return False


def _has_non_epa_dha_fatty_acid_panel(product: Dict[str, Any]) -> bool:
    """Return True for ALA / GLA / CLA / 3-6-9 style panels with no EPA/DHA.

    These are fatty-acid supplements, but not EPA/DHA omega-module products.
    They must not route via name-only "omega" marketing.
    """
    if _has_any_epa_dha_row(product):
        return False
    for ing in get_scoring_ingredients(product or {}, strict=True).rows:
        if not isinstance(ing, dict):
            continue
        canonical = str(ing.get("canonical_id") or "").strip().lower()
        if canonical in _NON_EPA_DHA_FATTY_ACID_CANONICALS:
            return True
        if (
            canonical in (_OMEGA_PARENT_CANONICALS | _OMEGA_INGREDIENT_CANONICALS)
            and _source_is_non_epa_dha_oil(ing)
            and not _source_has_epa_dha_identity(ing)
        ):
            return True
    return False


def _has_non_omega_positive_scorable_panel(product: Dict[str, Any]) -> bool:
    for ing in get_scoring_ingredients(product or {}, strict=True).rows:
        if not isinstance(ing, dict):
            continue
        if ing.get("scoring_input_kind") == "product_level_evidence":
            continue
        canonical = str(ing.get("canonical_id") or "").strip().lower()
        if not canonical or not _positive_quantity(ing):
            continue
        if canonical in _OMEGA_INGREDIENT_CANONICALS or canonical in _OMEGA_PARENT_CANONICALS:
            continue
        if canonical in _NON_EPA_DHA_FATTY_ACID_CANONICALS:
            continue
        return True
    return False


def _probiotic_payload(product: Dict[str, Any]) -> Dict[str, Any]:
    payload = (product or {}).get("probiotic_data") or (product or {}).get("probiotic_detail") or {}
    return payload if isinstance(payload, dict) else {}


def _positive_number(value: Any) -> bool:
    try:
        return value is not None and float(value) > 0
    except (TypeError, ValueError):
        return False


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _non_probiotic_scorable_count(product: Dict[str, Any]) -> int:
    """Count scorable active rows that are NOT probiotic strains.

    A large non-probiotic panel (a multivitamin's micronutrients, a protein's
    macros) means an accompanying strain is an adjunct, not the product identity.
    Count the scoring contract rows, not only IQD rows, so recovered actives and
    product-level enzyme/protein evidence participate in the route decision.
    """
    count = 0
    for row in _scoring_rows(product):
        if not isinstance(row, dict):
            continue
        tax = row.get("raw_taxonomy") if isinstance(row.get("raw_taxonomy"), dict) else {}
        category = str(tax.get("category") or row.get("category") or "").strip().lower()
        if category in {"probiotic", "probiotics", "bacteria"}:
            continue
        if str(row.get("dose_class") or "").strip().lower() == "probiotic_cfu":
            continue
        if str(row.get("evidence_type") or "").strip().lower() == "probiotic_cfu":
            continue
        canonical = str(row.get("canonical_id") or "").strip().lower()
        if canonical in {"fiber", "prebiotics"}:
            continue
        text = " ".join(
            str(row.get(key) or "")
            for key in ("name", "standardName", "standard_name", "raw_source_text", "category")
        ).lower()
        if any(
            term in text
            for term in (
                "probiotic",
                "lactobacillus",
                "bifidobacterium",
                "streptococcus",
                "saccharomyces",
                "bacillus",
                "limosilactobacillus",
                "cfu",
            )
        ):
            continue
        if any(term in text for term in ("dietary fiber", "prebiotic", "inulin", "fructooligosaccharide")):
            continue
        count += 1
    return count


def _title_has_non_probiotic_hero(name_text: str) -> bool:
    return bool(_NON_PROBIOTIC_HERO_TITLE_RE.search(name_text or ""))


def _title_hero_precedes_probiotic_signal(name_text: str) -> bool:
    hero = _NON_PROBIOTIC_HERO_TITLE_RE.search(name_text or "")
    probiotic = _PROBIOTIC_NAME_RE.search(name_text or "")
    return bool(hero and probiotic and hero.start() < probiotic.start())


def _has_non_probiotic_hero(product: Dict[str, Any], name_text: str) -> bool:
    """True when the product clearly advertises a non-probiotic primary identity
    via a specific taxonomy class or a hero keyword in the title.

    Used to guard the weakest probiotic signal (pure-strain, panel==0): a real
    zinc/protein/fiber product whose panel was lost upstream must not be promoted
    to probiotic just because its strain rows survived.
    """
    primary_type = _read_primary_type(product)
    if primary_type and primary_type not in _PROBIOTIC_VAGUE_TAXONOMY:
        return True
    return _title_has_non_probiotic_hero(name_text)


def _is_probiotic_class(product: Dict[str, Any], name_text: str) -> bool:
    """Return True for products with real probiotic identity evidence.

    This deliberately does not read legacy `supplement_type`. The taxonomy
    owns product class, but fresh artifacts can still have an over-specific
    primary_type (for example beauty_hair_skin_nails) while the probiotic
    enricher extracted named strains. Route probiotic when the product has
    enough probiotic_data to let the probiotic completeness gate decide:

      - named strains plus product-level CFU evidence, or
      - named strains plus explicit probiotic/synbiotic wording.

    The CFU/name guard prevents whole-food or botanical products with incidental
    non-quantified probiotic strain rows from being promoted to probiotic.
    """
    data = _probiotic_payload(product)
    if not data:
        return False

    is_product = bool(data.get("is_probiotic_product") or data.get("is_probiotic"))
    strain_count = int(data.get("total_strain_count") or 0)
    has_cfu = bool(data.get("has_cfu")) or _positive_number(data.get("total_cfu")) or _positive_number(
        data.get("total_billion_count")
    )
    total_billion = _number(data.get("total_billion_count"))
    total_cfu = _number(data.get("total_cfu"))
    high_cfu = total_billion >= _PROBIOTIC_HIGH_CFU_BILLIONS or total_cfu >= (
        _PROBIOTIC_HIGH_CFU_BILLIONS * 1_000_000_000
    )
    name_signal = bool(_PROBIOTIC_NAME_RE.search(name_text or ""))
    primary_type = _read_primary_type(product)

    if not is_product or strain_count <= 0:
        return False

    non_probiotic_panel = _non_probiotic_scorable_count(product)

    # Pure multi-strain products are unambiguously probiotic even without CFU
    # disclosure or a "probiotic" name token. panel==0 means the strains are the
    # ONLY scorable identity, so this cannot capture a vitamin/mineral/protein
    # carrying adjunct strains (those have panel >= 1). The hero guard additionally
    # blocks a product that advertises a non-probiotic identity (zinc/protein/fiber
    # title or specific taxonomy) but whose real panel was lost upstream.
    if (
        non_probiotic_panel == 0
        and strain_count >= _PROBIOTIC_PURE_STRAIN_MIN
        and not _has_non_probiotic_hero(product, name_text)
    ):
        return True

    if (
        primary_type == "probiotic"
        and non_probiotic_panel == 0
        and strain_count >= 1
        and not _has_non_probiotic_hero(product, name_text)
    ):
        return True

    # Otherwise require CFU-or-name evidence (guards incidental strains in
    # whole-food / botanical products from being promoted), plus the role-aware
    # strain-dominance gate: an adjunct strain must not hijack a product whose
    # dominant scorable identity is something else (multivitamin, whey, hydration).
    if not (has_cfu or name_signal):
        return False

    if primary_type and primary_type not in _PROBIOTIC_VAGUE_TAXONOMY and not name_signal:
        # Specific non-probiotic taxonomy (multivitamin, single vitamin/mineral,
        # fiber, immune, etc.) should not be hijacked by tiny probiotic adjuncts.
        # Allow override without a name token only for genuinely high-CFU products
        # with a small adjunct panel, e.g. immune probiotic + vitamin C/zinc.
        if not (high_cfu and non_probiotic_panel <= _PROBIOTIC_ADJUNCT_PANEL_MAX):
            return False

    if name_signal and non_probiotic_panel > 0 and _title_hero_precedes_probiotic_signal(name_text):
        return False

    if non_probiotic_panel > 0 and not name_signal:
        if _title_has_non_probiotic_hero(name_text):
            return False
        if not high_cfu:
            return False

    if strain_count >= non_probiotic_panel:
        return True
    if non_probiotic_panel <= _PROBIOTIC_ADJUNCT_PANEL_MAX and name_signal:
        return True
    return False


_MARINE_OMEGA_SOURCE_RE = re.compile(
    r"\b("
    r"fish\s*oil|fish\s+body\s+oil|salmon|anchovy|sardine|mackerel|menhaden|"
    r"herring|cod\s+liver|krill|algae?\s*oil|algal|calamari|squid|marine"
    r")\b",
    re.IGNORECASE,
)


def _omega_product_source_text(product: Dict[str, Any]) -> str:
    parts = [
        str(product.get(k) or "")
        for k in ("product_name", "fullName", "brand_name", "bundleName")
    ]
    rows = product.get("ingredient_quality_data") or product.get("active_ingredients") or []
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict):
            parts.append(_row_source_text(row))
    return " ".join(parts)


def _product_lacks_epa_dha_identity(product: Dict[str, Any]) -> bool:
    """True when the product source is an explicit non-EPA/DHA plant/seed/MCT oil
    (flax/ALA/chia/hemp/fiber/seed/MCT/coconut) with NO marine source and NO
    explicit EPA/DHA token — i.e. plant 'omega-3' (ALA), which must route generic,
    not the EPA/DHA omega module, even if a row was mis-canonicalized upstream."""
    src = _omega_product_source_text(product)
    return bool(
        _NON_EPA_DHA_SOURCE_RE.search(src)
        and not _EPA_DHA_SOURCE_RE.search(src)
        and not _MARINE_OMEGA_SOURCE_RE.search(src)
    )


def _is_omega_class(product: Dict[str, Any], name_text: str) -> bool:
    """Detect omega-class routing signals.

    Strict triggers — scoring consumes taxonomy/ingredient contracts only:
      1. ingredient_quality_data has canonical_id ∈ {epa, dha, epa_dha}
         with positive quantity (strongest signal — enricher already
         canonicalized the identity)
      2. taxonomy primary_type routes to omega before this helper is called

    HISTORICAL — a 5th trigger (category_breakdown.fatty_acid plurality)
    was removed 2026-05-20 after a real-catalog audit caught ~250 false
    positives: CLA / Borage Oil (GLA) / Flax Seed Oil (ALA-only) / MCT /
    Liposomal Glutathione (lecithin) all count as fatty_acid in the
    enricher's category_breakdown but NONE are EPA/DHA-bearing. The
    plurality check was redundant — every legitimate omega product
    (Sports Research, Nordic Naturals Ultimate Omega, Garden of Life
    Advanced Omega, etc.) is already caught by _has_omega_ingredient
    because the enricher canonicalizes EPA/DHA from the ingredient panel.
    Per the dev's 2026-05-20 feedback: ALA is alpha-linolenic acid,
    a different molecule from EPA/DHA; ALA-only products route to
    generic (where ALA gets the IOM AI when the rda_optimal_uls fix
    lands), not omega.
    """
    # 0. Hard guard: an explicit non-EPA/DHA plant/seed/MCT source (ALA/flax/
    #    chia/hemp/fiber/seed/MCT/coconut) with NO marine source and NO explicit
    #    EPA/DHA token is plant 'omega-3' (ALA) — it must route generic, never the
    #    EPA/DHA omega module, even if a panel row was mis-canonicalized to
    #    epa/dha/fish_oil upstream (the row-level checks below run too late because
    #    _has_omega_ingredient short-circuits on the polluted canonical).
    if _product_lacks_epa_dha_identity(product):
        return False

    # 1. Strongest signal: EPA/DHA is a primary panel identity.
    if _has_omega_ingredient(product):
        return True

    # ALA / GLA / CLA / 3-6-9 products may use omega marketing language,
    # but they do not belong in the EPA/DHA omega module unless EPA/DHA is
    # actually disclosed in the panel. 3-6-9 labels with real EPA/DHA rows
    # should continue through the normal omega checks below.
    if _OMEGA_369_RE.search(name_text) and not _has_any_epa_dha_row(product):
        return False
    if _OMEGA_EFA_RE.search(name_text or ""):
        return _has_any_epa_dha_row(product) or _has_omega_scoring_evidence(product)
    if _has_non_epa_dha_fatty_acid_panel(product):
        return False

    lowered = (name_text or "").lower()
    if any(token in lowered for token in _OMEGA_STRONG_OIL_NAME_KEYWORDS):
        if _OMEGA_STANDALONE_RE.search(name_text or ""):
            return True
        if _has_omega_scoring_evidence(product):
            return True
        primary_type = _read_primary_type(product)
        if primary_type == "omega_3":
            return True
        if _has_non_omega_product_level_evidence(product):
            return False
        return not _has_non_omega_positive_scorable_panel(product)
    if any(token in lowered for token in _OMEGA_NAME_KEYWORDS):
        if _has_omega_scoring_evidence(product):
            return True
        if _OMEGA_STANDALONE_RE.search(name_text or ""):
            return True
        primary_type = _read_primary_type(product)
        return primary_type == "omega_3"
    if _has_omega_scoring_evidence(product):
        return True
    return bool(_OMEGA_STANDALONE_RE.search(name_text or ""))


def _is_b_complex_route_eligible(product: Dict[str, Any], name_text: str) -> bool:
    """Return True for true B-complex panels, not targeted beauty/energy SKUs.

    Taxonomy can classify products with three B vitamins plus functional
    actives as b_complex. Those should remain generic unless the label
    explicitly says B-complex or the panel has a broad B-vitamin spread.
    """
    lowered = (name_text or "").lower()
    if "b-complex" in lowered or "b complex" in lowered:
        return True

    b_vitamins: set[str] = set()
    non_b_scorable = 0
    for ing in get_scoring_ingredients(product or {}, strict=True).rows:
        if not isinstance(ing, dict):
            continue
        canonical = str(ing.get("canonical_id") or "").strip().lower()
        if not canonical:
            continue
        if canonical in _B_VITAMIN_CANONICALS:
            b_vitamins.add(canonical)
        else:
            non_b_scorable += 1

    return len(b_vitamins) >= 4 and len(b_vitamins) > non_b_scorable


def _is_multivitamin_route_eligible(product: Dict[str, Any], name_text: str) -> bool:
    """Parity mirror of scoring_input_contract._route_is_multivitamin_eligible.
    Guards the `multivitamin` taxonomy route by content (broad multi-nutrient
    panel) instead of trusting the native primary_type alone. Explicit multi*
    naming is taken at its word (mirrors b_complex)."""
    lowered = (name_text or "").lower()
    if (
        "multivitamin" in lowered
        or "multi-vitamin" in lowered
        or "multi vitamin" in lowered
        or "multimineral" in lowered
    ):
        return True
    canonicals = _positive_canonicals(product)
    if len(canonicals & _MULTI_PANEL_CANONICALS) >= 4:
        return True
    if _read_primary_type(product) == "multivitamin":
        return (
            _positive_scorable_row_count(product)
            >= _MULTIVITAMIN_BROAD_PANEL_MIN
        )
    return False


def _read_legacy_multivitamin_type(product: Dict[str, Any]) -> str:
    payload = (product or {}).get("supplement_type")
    if not isinstance(payload, dict):
        return ""
    value = payload.get("type")
    return str(value or "").strip().lower()


def _multi_panel_group_count(canonicals: set[str]) -> int:
    groups = set()
    if canonicals & _B_VITAMIN_CANONICALS:
        groups.add("b_vitamins")
    if canonicals & _NON_B_VITAMIN_CANONICALS:
        groups.add("vitamins")
    if canonicals & _MINERAL_CANONICALS:
        groups.add("minerals")
    if canonicals & _MULTI_SUPPORT_CANONICALS:
        groups.add("support_nutrients")
    return len(groups)


def _has_broad_legacy_multivitamin_panel(product: Dict[str, Any]) -> bool:
    """True only for old enriched themed multi-packs with a real broad panel.

    This is the sole v4 router legacy-type fallback. It fixes products whose
    normalized taxonomy stores the theme (immune/sleep/herbal) while legacy
    type still correctly says multivitamin. The broad-panel gate prevents the
    old over-classification failures from returning.
    """
    if _read_legacy_multivitamin_type(product) != "multivitamin":
        return False
    if _read_primary_type(product) in _LEGACY_MULTI_FALLBACK_EXCLUDED_PRIMARY_TYPES:
        return False
    canonicals = _positive_canonicals(product)
    multi_nutrients = canonicals & _MULTI_PANEL_CANONICALS
    return (
        len(multi_nutrients) >= _LEGACY_MULTIVITAMIN_MIN_MULTI_NUTRIENTS
        and _positive_scorable_row_count(product) >= _MULTIVITAMIN_BROAD_PANEL_MIN
        and _multi_panel_group_count(multi_nutrients) >= 3
    )


def _positive_scorable_row_count(product: Dict[str, Any]) -> int:
    count = 0
    for row in _scoring_rows(product):
        if row.get("scoring_input_kind") == "product_level_evidence":
            continue
        if _positive_quantity(row):
            count += 1
    return count


def _product_label_text(product: Dict[str, Any]) -> str:
    """Text that belongs to the product label, excluding brand/bundle context."""
    return " ".join(str((product or {}).get(k) or "") for k in ("product_name", "fullName"))


def _has_broad_prenatal_multi_panel(product: Dict[str, Any]) -> bool:
    canonicals = _positive_canonicals(product)
    multi_nutrients = canonicals & _MULTI_PANEL_CANONICALS
    prenatal_anchors = canonicals & _PRENATAL_PANEL_ANCHORS
    # Fallback for under-classified prenatal gummies/multis: require a broad
    # micronutrient panel, not merely one prenatal-adjacent nutrient.
    return len(multi_nutrients) >= 5 and len(prenatal_anchors) >= 2


def _is_prenatal_multi_intent(product: Dict[str, Any], name_text: str) -> bool:
    """Return True only for prenatal products that should use the multi rubric.

    Prenatal wording in a bundle/program name is not enough. Real catalog
    examples include a single Calcium 600 item inside a "Prenatal Program" and
    herbal "Prenatal Tummy Comfort"; neither should be crushed by prenatal
    folate/iron/iodine/choline/DHA floors.
    """
    if not _PRENATAL_KEYWORDS.search(_product_label_text(product)):
        return False

    primary_type = _read_primary_type(product)
    if primary_type == "multivitamin":
        return True
    if primary_type == "b_complex":
        return _is_b_complex_route_eligible(product, name_text)
    return _has_broad_prenatal_multi_panel(product)


def _positive_canonicals(product: Dict[str, Any]) -> set[str]:
    canonicals: set[str] = set()
    for ing in _scoring_rows(product):
        if ing.get("scoring_input_kind") == "product_level_evidence":
            continue
        canonical = str(ing.get("canonical_id") or "").strip().lower()
        if canonical and _positive_quantity(ing):
            canonicals.add(canonical)
    return canonicals


def _has_sports_primary_dose_evidence(product: Dict[str, Any]) -> bool:
    """True when the scoring contract explicitly provides sports dose evidence.

    Generic product-level evidence such as conservative blend/header anchors is
    intentionally not a class signal. Those rows can recover dose scoring, but
    they must not override taxonomy into the sports module.
    """
    for ing in _scoring_rows(product):
        if ing.get("scoring_input_kind") != "product_level_evidence":
            continue
        if str(ing.get("evidence_type") or "").strip().lower() != "sports_primary_dose":
            continue
        if _positive_quantity(ing):
            return True
    return False


def _has_product_level_protein_mass(product: Dict[str, Any]) -> bool:
    protein_ids = {"protein", *_SPORTS_PROTEIN_CANONICALS}
    for ing in _scoring_rows(product):
        if ing.get("scoring_input_kind") != "product_level_evidence":
            continue
        if str(ing.get("evidence_type") or "").strip().lower() not in {"sports_primary_dose", "blend_anchor_mass"}:
            continue
        identities = {
            str(ing.get("canonical_id") or "").strip().lower(),
            str(ing.get("evidence_canonical_id") or "").strip().lower(),
            str(ing.get("scoring_parent_id") or "").strip().lower(),
            str(ing.get("clean_identity_id") or "").strip().lower(),
        }
        if identities & protein_ids and _positive_quantity(ing):
            return True
    return False


def _has_product_level_single_sports_mass(product: Dict[str, Any]) -> bool:
    for ing in _scoring_rows(product):
        if ing.get("scoring_input_kind") != "product_level_evidence":
            continue
        if str(ing.get("evidence_type") or "").strip().lower() not in {"sports_primary_dose", "blend_anchor_mass"}:
            continue
        identities = {
            str(ing.get("canonical_id") or "").strip().lower(),
            str(ing.get("evidence_canonical_id") or "").strip().lower(),
            str(ing.get("scoring_parent_id") or "").strip().lower(),
            str(ing.get("clean_identity_id") or "").strip().lower(),
        }
        if identities & _SPORTS_SINGLE_CANONICALS and _positive_quantity(ing):
            return True
    return False


def _has_collagen_primary_identity(product: Dict[str, Any], name_text: str) -> bool:
    canonicals = _positive_canonicals(product)
    has_collagen_row = bool(canonicals & {"collagen", "collagen_peptides", "hydrolyzed_collagen"})
    has_collagen_title = bool(_COLLAGEN_TITLE_RE.search(name_text or ""))
    if not (has_collagen_row or has_collagen_title):
        return False
    if canonicals & _SPORTS_PROTEIN_CANONICALS:
        return False
    if _SPORTS_TRUE_PROTEIN_NAME_RE.search(name_text or "") and not has_collagen_title:
        return False
    return True


def _is_sports_class(product: Dict[str, Any], name_text: str) -> bool:
    """Return True for explicit sports-nutrition products.

    This is deliberately narrower than "any amino acid" or
    "protein_powder taxonomy". The fresh corpus has many amino-acid products
    (NAC, L-theanine, SAM-e, lysine) and protein-like products (keratin,
    lactoferrin) that are not sports products and must remain generic.
    """
    primary_type = _read_primary_type(product)
    sports_intent = primary_type == "pre_workout" or bool(_SPORTS_PREWORKOUT_RE.search(name_text or ""))
    if _has_collagen_primary_identity(product, name_text):
        return False
    if _has_sports_primary_dose_evidence(product):
        return True

    canonicals = _positive_canonicals(product)
    lowered = name_text or ""

    if canonicals & _SPORTS_PROTEIN_CANONICALS:
        return primary_type == "protein_powder" or bool(_SPORTS_PROTEIN_NAME_RE.search(lowered))
    if _has_product_level_protein_mass(product) and _SPORTS_PROTEIN_NAME_RE.search(lowered):
        return True
    if primary_type == "protein_powder" and _SPORTS_PROTEIN_NAME_RE.search(lowered):
        return True

    if _BCAA_CANONICALS.issubset(canonicals) and (
        primary_type in {"amino_acid", "pre_workout"} or _SPORTS_SINGLE_ACTIVE_NAME_RE.search(lowered)
    ):
        return True
    if len(canonicals & _EAA_CANONICALS) >= 6 and (
        primary_type in {"amino_acid", "pre_workout"} or _SPORTS_SINGLE_ACTIVE_NAME_RE.search(lowered)
    ):
        return True

    if canonicals & _SPORTS_SINGLE_CANONICALS:
        if _SPORTS_NAME_EXCLUSION_RE.search(lowered):
            return False
        return sports_intent or bool(_SPORTS_SINGLE_ACTIVE_NAME_RE.search(lowered))
    if _has_product_level_single_sports_mass(product):
        if _SPORTS_NAME_EXCLUSION_RE.search(lowered):
            return False
        return sports_intent or bool(_SPORTS_SINGLE_ACTIVE_NAME_RE.search(lowered))

    return False


# Taxonomy primary_type → v4 module mapping. The taxonomy emits 20 types
# (see scripts/data/product_type_vocab.json); v4 has 4 scoring modules.
# Most product classes route to `generic` because their scoring rubric is
# adequately handled by the generic dimensions; only probiotic / multi /
# omega have dedicated modules with class-specific dose / form / evidence
# rubrics.
_TAXONOMY_TO_MODULE = {
    "probiotic": "probiotic",
    "multivitamin": "multi_or_prenatal",
    "b_complex": "multi_or_prenatal",  # B-complex is a multi-vitamin variant
    "omega_3": "omega",
    # Everything else routes to generic — listed explicitly so future
    # taxonomy types are caught by the unknown-key fallthrough below:
    "single_vitamin": "generic",
    "single_mineral": "generic",
    "vitamin_mineral_combo": "generic",
    "herbal_botanical": "generic",
    "protein_powder": "generic",
    "collagen": "generic",
    "greens_powder": "generic",
    "electrolyte": "generic",
    "pre_workout": "generic",
    "amino_acid": "generic",
    "fiber_digestive": "generic",
    "sleep_support": "generic",
    "immune_support": "generic",
    "joint_support": "generic",
    "beauty_hair_skin_nails": "generic",
    "general_supplement": "generic",
}
_LEGACY_MULTI_FALLBACK_EXCLUDED_PRIMARY_TYPES = {
    "amino_acid",
    "collagen",
    "fiber_digestive",
    "greens_powder",
    "omega_3",
    "pre_workout",
    "probiotic",
    "protein_powder",
}


def _read_primary_type(product: Dict[str, Any]) -> str:
    """Return the taxonomy `primary_type` if present, else empty string.

    Pipeline writes the field at two paths (set by enrich_supplements_v3
    and preserved by score_supplements):
      product["primary_type"]
      product["supplement_taxonomy"]["primary_type"]
    Both are read for resilience.
    """
    direct = (product or {}).get("primary_type")
    if isinstance(direct, str) and direct.strip():
        return direct.strip().lower()
    taxonomy = (product or {}).get("supplement_taxonomy") or {}
    if isinstance(taxonomy, dict):
        nested = taxonomy.get("primary_type")
        if isinstance(nested, str) and nested.strip():
            return nested.strip().lower()
    return ""


def _legacy_class_for_product(product: Dict[str, Any]) -> str:
    """Return the current v4 route implementation.

    Reads `primary_type` from the supplement taxonomy as the canonical
    signal. Scoring treats product names and legacy categories as display
    context, not clinical routing inputs.

    Never raises on malformed input. Never returns None or a value outside
    VALID_CLASSES. Missing or unknown signals fall through to `generic`.
    """
    primary_type = _read_primary_type(product)
    name_text = " ".join(
        str((product or {}).get(k) or "")
        for k in ("product_name", "fullName", "brand_name", "bundleName")
    )

    # Priority 1: probiotic. Taxonomy can be stale or polluted by upstream
    # strain extraction, so the final route requires validated probiotic content
    # evidence. Explicit greens taxonomy is not under-classified: greens/
    # superfood products can carry probiotic strains without becoming
    # probiotic-module products.
    if primary_type != "greens_powder" and _is_probiotic_class(product, name_text):
        return "probiotic"

    # Priority 2: prenatal multi intent -> multi_or_prenatal for products like
    # Prenatal Gummies / Pregnancy Vitamins, whose prenatal use case has stricter
    # dose/safety expectations (folate, iron, iodine critical-nutrient floors) the
    # multi module handles. EXCEPTION: a single-purpose "Prenatal DHA" whose actives
    # are PRIMARILY an EPA/DHA omega panel is an omega supplement, not an incomplete
    # prenatal multi — routing it to multi_or_prenatal crushes it on prenatal-panel
    # coverage for nutrients it never contained (Thorne Prenatal DHA 650 mg -> POOR).
    # Route those to omega so they're scored on EPA/DHA dosing. Single-mineral /
    # herbal prenatal-support products remain generic unless the panel itself is
    # a broad prenatal multi.
    # Prenatal-probiotic was already handled by Priority 1 above.
    if _PRENATAL_KEYWORDS.search(_product_label_text(product)):
        if _has_primary_omega_panel(product):
            return "omega"
        if _is_prenatal_multi_intent(product, name_text):
            return "multi_or_prenatal"

    # Priority 3: sports. Keep this before multi/b-complex because real
    # pre-workout products can carry enough B vitamins for b_complex taxonomy.
    # The helper is intentionally conservative so ordinary amino-acid and
    # protein-like products stay generic.
    if _is_sports_class(product, name_text):
        return "sports"

    if (
        _EXPLICIT_MULTIVITAMIN_NAME_RE.search(_product_label_text(product))
        and _is_multivitamin_route_eligible(product, name_text)
    ):
        return "multi_or_prenatal"

    # Priority 4: taxonomy primary_type — canonical signal when present.
    # Maps the 20 taxonomy types to the 4 v4 modules. Unknown taxonomy
    # values (new types added later that aren't in _TAXONOMY_TO_MODULE)
    # fall through to the omega / generic logic below rather than crashing.
    if primary_type:
        module = _TAXONOMY_TO_MODULE.get(primary_type)
        if module == "multi_or_prenatal":
            if primary_type == "b_complex" and not _is_b_complex_route_eligible(product, name_text):
                return "generic"
            if primary_type == "multivitamin" and not _is_multivitamin_route_eligible(product, name_text):
                return "generic"
            return "multi_or_prenatal"
        if module == "omega":
            return "omega" if _is_omega_class(product, name_text) else "generic"
        if module == "sports":
            return "sports" if _is_sports_class(product, name_text) else "generic"
        if module == "generic":
            # Taxonomy is authoritative for generic classes, but the
            # physical panel fact of disclosed EPA/DHA still wins. Explicit
            # EPA/DHA or fish-oil label identity also routes omega so the
            # omega completeness gate can block parent-mass / undisclosed
            # EPA-DHA products instead of letting generic score unrelated
            # vitamins. ALA / 3-6-9 / fatty-acid blends are still guarded in
            # _is_omega_class unless EPA/DHA is actually disclosed.
            if _is_omega_class(product, name_text):
                return "omega"
            if _has_broad_legacy_multivitamin_panel(product):
                return "multi_or_prenatal"
            return "generic"
        # Unknown taxonomy type: fall through to legacy omega / multi fallback
        # rather than crashing.

    # Priority 4: omega panel-canonical detection.
    # The panel-canonical (canonical_id ∈ {epa,dha,epa_dha} with positive
    # quantity) is the strongest omega signal — it operates on the
    # enricher's canonicalized identity. Name-keyword and standalone
    # EPA/DHA fallbacks catch labels where canonicalization didn't run.
    if _is_omega_class(product, name_text):
        return "omega"
    if _has_broad_legacy_multivitamin_panel(product):
        return "multi_or_prenatal"

    # Priority 5: generic catch-all.
    return "generic"


def class_for_product(product: Dict[str, Any]) -> str:
    """Return one of VALID_CLASSES via ScoringClassification v1.

    The private legacy implementation remains in this module as the
    compatibility parity baseline. The public router now consumes the single
    classification seam so downstream callers no longer need to know where the
    route came from.
    """
    try:
        contract = build_scoring_classification(product)
        result = contract.get("route_module")
    except Exception:  # pragma: no cover - router is a total public API
        return "generic"
    return result if result in VALID_CLASSES else "generic"

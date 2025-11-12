"""
Constants and configuration for DSLD data cleaning pipeline
"""
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
DATA_DIR = SCRIPTS_DIR / "data"
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

# Reference data files
INGREDIENT_QUALITY_MAP = DATA_DIR / "ingredient_quality_map.json"
STANDARDIZED_BOTANICALS = DATA_DIR / "standardized_botanicals.json"
ENHANCED_DELIVERY = DATA_DIR / "enhanced_delivery.json"
SYNERGY_CLUSTER = DATA_DIR / "synergy_cluster.json"
BANNED_RECALLED = DATA_DIR / "banned_recalled_ingredients.json"
HARMFUL_ADDITIVES = DATA_DIR / "harmful_additives.json"
ALLERGENS = DATA_DIR / "allergens.json"
PROPRIETARY_BLENDS = DATA_DIR / "proprietary_blends_penalty.json"
CLINICAL_STUDIES = DATA_DIR / "backed_clinical_studies.json"
TOP_MANUFACTURERS = DATA_DIR / "top_manufacturers_data.json"
ABSORPTION_ENHANCERS = DATA_DIR / "absorption_enhancers.json"
RDA_OPTIMAL_ULS = DATA_DIR / "rda_optimal_uls.json"
RDA_THERAPEUTIC_DOSING = DATA_DIR / "rda_therapeutic_dosing.json"
UNIT_MAPPINGS = DATA_DIR / "unit_mappings.json"
INGREDIENT_WEIGHTS = DATA_DIR / "ingredient_weights.json"
PASSIVE_INACTIVE_INGREDIENTS = DATA_DIR / "passive_inactive_ingredients.json"
NON_HARMFUL_ADDITIVES = DATA_DIR / "non_harmful_additives.json"
BOTANICAL_INGREDIENTS = DATA_DIR / "botanical_ingredients.json"

# Output subdirectories
OUTPUT_CLEANED = OUTPUT_DIR / "cleaned"
OUTPUT_NEEDS_REVIEW = OUTPUT_DIR / "needs_review"
OUTPUT_INCOMPLETE = OUTPUT_DIR / "incomplete"
OUTPUT_UNMAPPED = OUTPUT_DIR / "unmapped"

# Field mappings for normalization
UNIT_CONVERSIONS = {
    # Vitamin-specific IU conversions (context-aware)
    "IU": {
        "vitamin d": 0.025, "vitamin d3": 0.025, "vitamin d2": 0.025,  # IU to mcg
        "vitamin a": 0.3, "retinol": 0.3,  # IU to mcg RAE
        "vitamin e": 0.67, "alpha-tocopherol": 0.67,  # IU to mg
        "beta carotene": 0.6  # IU to mcg
    },
    # Standard metric conversions
    "gram": {"mg": 1000, "mcg": 1000000, "g": 1},
    "milligram": {"mg": 1, "mcg": 1000, "g": 0.001},
    "microgram": {"mcg": 1, "mg": 0.001, "g": 0.000001},
    # Additional units
    "kilogram": {"g": 1000, "mg": 1000000, "mcg": 1000000000},
    "ounce": {"g": 28.35, "mg": 28350},
    "pound": {"g": 453.6, "mg": 453600}
}

# Nutritional facts that should NOT be treated as supplement ingredients
# These are macro/nutritional components reported on food labels, not active ingredients
EXCLUDED_NUTRITION_FACTS = {
    # Energy and macronutrients
    "calories", "energy", "kcal", "cal",
    "total fat", "fat", "saturated fat", "trans fat", "polyunsaturated fat", "monounsaturated fat",
    "cholesterol", "total cholesterol", "dietary cholesterol",
    "total carbohydrates", "carbohydrates", "carbs", "total carbs", "total carbohydrate",
    "dietary fiber", "fiber", "soluble fiber", "insoluble fiber",
    "sugars", "total sugars", "added sugars", "sugar", "natural sugars",
    "sugar alcohols", "sugar alcohol", "polyols",
    "protein", "total protein", "proteins",
    "water", "moisture",
    # Common electrolytes/minerals when listed as basic nutrition facts
    "sodium", "salt", "sodium chloride",
    # Other nutritional labels
    "serving size", "servings per container", "amount per serving"
}

# Label phrases and headers that should be excluded from ingredient processing
# IMPORTANT: All entries must be lowercase for proper comparison with preprocessed text
EXCLUDED_LABEL_PHRASES = {
    # Percentage headers (all lowercase)
    "contains <2% of:", "contains <2% of", "contains < 2% of",
    "contains 2% or less of the following", "contains less than 2% of",
    "contains less than 2% of the following", "contains 2% or less of",
    "less than 2% of", "less than 2%", "<2% of",
    "less than 2% of:", "contains less than 2%", "less than 1% of",

    # Other carbohydrate variations
    "other carbohydrates", "other carbohydrate", "other carbs",

    # Allergen warnings
    "may contain one or more of the following", "may contain one or more of the following:",
    "may contain", "contains one or more of the following",

    # Nutritional labels not in EXCLUDED_NUTRITION_FACTS
    "calories from fat", "calories from saturated fat",

    # Generic flavor/water descriptors that should be handled separately
    "flavor, natural", "artificial and natural flavorings",
    "water, purified",

    # Other common label phrases
    "other ingredients", "inactive ingredients", "active ingredients",
    "contains", "includes", "consisting of", "also contains",

    # Invalid or placeholder values
    "none", "n/a", "not applicable", "null", "unknown",

    # Descriptive text that's not ingredients
    "naturally sweet", "stomach", "liver", "energized nutrients",
    "acid reflux", "acid redux",

    # Quantity/composition descriptions
    "contains < 2% of", "contains 2% or less of the following",
    "may contain one or more of the following", "may contain one or more of the following:",
    "proprietary blend of",
    "from 800 mg of premium cultivar elderberries",
    "includes added sugar",
    "natural food base blend combination"
}

# Nutritional warnings to track for UI display (but not map as ingredients)
NUTRITIONAL_WARNING_FIELDS = {
    "sugar_content": [
        "sugars", "added sugars", "sugar", "organic sugar", "liquid sugar",
        "fructose", "fructose syrup", "fruit juice", "fruit juice concentrate",
        "fruitsugar", "total sugars"
    ],
    "saturated_fat": ["saturated fat", "saturated fats"],
    "sodium_content": ["sodium", "salt"],
    "trans_fat": ["trans fat", "trans fats"],
    "cholesterol": ["cholesterol", "dietary cholesterol"]
}

# Required fields for completeness check
REQUIRED_FIELDS = {
    "critical": [
        "id",
        "fullName",
        "brandName",
        "ingredientRows"
    ],
    "important": [
        "upcSku",
        "productType",
        "physicalState"
    ],
    "optional": [
        "servingsPerContainer",
        "thumbnail",
        "netContents",
        "targetGroups",
        "images",
        "contacts",
        "events",
        "statements",
        "claims",
        "servingSizes"
    ]
}

# Severity levels
SEVERITY_LEVELS = ["low", "moderate", "high"]

# Risk levels
RISK_LEVELS = ["low", "moderate", "high"]

# Harmful categories
HARMFUL_CATEGORIES = [
    "sweetener",
    "preservative",
    "dye",
    "flavor",
    "filler",
    "solvent",
    "none"
]

# Statement types to extract
STATEMENT_TYPES_OF_INTEREST = [
    "Seals/Symbols",
    "Formulation re: Does NOT Contain",
    "Formulation re: Organic",
    "Formulation re: Vegetarian/Vegan",
    "Formula re: Kosher",
    "Precautions re: Allergies",
    "FDA Disclaimer Statement",
    "Storage"
]

# Certification patterns - Comprehensive list based on industry research
CERTIFICATION_PATTERNS = {
    # Core Quality Certifications (Highest Priority)
    "NSF-Contents-Certified": r"NSF\s*(Contents\s*Certified|/ANSI\s*173)",
    "NSF-Certified-Sport": r"NSF\s*(Certified\s*for\s*Sport|Sport)",
    "NSF-General": r"NSF\s*(Certified|International)",
    "USP-Verified": r"USP\s*(Verified|Grade|<\d+>|\s+standards)",
    "ConsumerLab-Approved": r"ConsumerLab\s*(Tested|Approved|CL\s*Approved)",
    "Informed-Choice": r"Informed[\s-]*Choice",
    "Informed-Sport": r"Informed[\s-]*Sport",
    "BSCG-Drug-Free": (
        r"BSCG\s*(Certified\s*Drug\s*Free|Banned\s*Substances\s*Control\s*Group)"
    ),

    # Manufacturing and GMP Audits
    "GMP-General": (
        r"(GMP|Good\s*Manufacturing\s*Practices)\s*(Certified|facility|manufactured|compliant|registered)?"
        r"|produced\s+in\s+(a\s+)?GMP\s+facility"
    ),
    "NSF-GMP": r"NSF\s*GMP\s*(Registration|Registered|Certified)",
    "NPA-GMP": r"(NPA|Natural\s*Products\s*Association)\s*GMP",
    "UL-GMP": r"UL\s*(Solutions\s*)?GMP",
    "cGMP": r"cGMP\s*(Certified|Compliant|21\s*CFR|Part\s*210|Part\s*211)",

    # Specialty and Category Certifications
    "AOAC-Validated": r"AOAC[\s-]*(validated|method)",
    "Non-GMO-Project": r"Non[\s-]*GMO\s*Project\s*Verified",
    "Non-GMO-General": r"Non[\s-]*GMO(?!\s*Project)",
    "Gluten-Free-GFCO": r"(GFCO|Gluten[\s-]*Free\s*Certification\s*Organization)",
    "Gluten-Free-General": (
        r"(Certified\s*Gluten[\s-]*Free|Gluten[\s-]*Free\s*Certified)"
        r"(?!\s*(GFCO|Certification\s*Organization))"
    ),
    "Certified-Vegan": r"Certified\s*Vegan|Vegan\s*Action|VegeCert",
    "Certified-Vegetarian": r"Certified\s*Vegetarian",
    "Kosher-OU": r"OU\s*Kosher|\bOU\b",
    "Kosher-OK": r"OK\s*Kosher|\bOK\b(?=.*kosher)",
    "Kosher-Star-K": r"Star[\s-]*K",
    "Kosher-General": r"Kosher(?!\s*(OU|OK|Star))",
    "Halal-IFANCA": r"IFANCA|Islamic\s*Food\s*and\s*Nutrition\s*Council",
    "Halal-General": r"Halal\s*Certified|Certified\s*Halal",
    "Organic-USDA": r"(USDA\s*Organic|Certified\s*Organic)",
    "Marine-Sustainability": (
        r"(Friends\s*of\s*the\s*Sea|MarinTrust|MSC\s*Chain[\s-]*of[\s-]*Custody)"
    ),
    "IFOS": r"IFOS\s*(Certified|5[\s-]*Star|International\s*Fish\s*Oil\s*Standards)?",
    "IGEN": r"IGEN\s*(Non[\s-]*GMO)?",

    # Emerging/Regional Programs
    "TGA-Listed": r"TGA[\s-]*Listed|ARTG|Therapeutic\s*Goods\s*Administration",
    "Health-Canada-NNHP": r"(Health\s*Canada|NNHP|NPN|Natural\s*Product\s*Number)",
    "Eurofins-Certified": r"Eurofins\s*Certified",
    "Labdoor": r"Labdoor\s*(Grade|Tested|Ranked)",

    # Additional Quality Markers
    "Third-Party-Tested": (
        r"(Third[\s-]*Party|3rd[\s-]*Party)[\s-]*(Tested|Verified|inspected)"
    ),
    "FDA-Inspected": (
        r"FDA[\s-]*(regulated|inspected|registered)[\s-]*(facility|supplement|dietary)"
    ),
    "ISO-Certified": r"ISO\s*\d+\s*Certified",
    "Pharmaceutical-Grade": r"Pharmaceutical\s*Grade",

    # B-Corporation and Sustainability
    "B-Corporation": r"(Certified\s*)?B[\s-]*Corporation|B[\s-]*Corp",
    "Sustainable": r"Sustainably\s*(Sourced|Harvested)",
    "Fair-Trade": r"Fair\s*Trade\s*Certified"
}

# Enhanced exclusion patterns for non-ingredients
ENHANCED_EXCLUSION_PATTERNS = [
    # Percentage patterns (comprehensive)
    r"less\s+than\s+\d+%.*",
    r"contains?\s+less\s+than\s+\d+%.*",
    r"contains?\s*<?\s*\d+%\s+of.*",
    r"<\s*\d+%\s+of.*",
    r"\d+%\s+or\s+less.*",

    # Capsule and form descriptions
    r"softgel\s+capsule",
    r"veggie\s+capsule",
    r"vegetarian\s+capsule",
    r"gelatin\s+capsule",
    r"hard\s+shell\s+capsule",
    r"capsule\s+shell",

    # Common non-ingredient phrases
    r"other\s+carbohydrate.*",
    r"serving\s+size.*",
    r"amount\s+per\s+serving.*",
    r"daily\s+value.*",
    r"percent\s+daily\s+value.*",

    # Processing aids and form descriptors
    r"pharmaceutical\s+glaze",
    r"enteric\s+coating",
    r"time\s+release\s+coating",
    r"tablet\s+coating"
]

# Enhanced proprietary blend parsing patterns
# Pattern for ingredient + dose extraction - improved to handle more cases
DOSE_PATTERN = r'^(.+?)\s*\(?(\d+(?:\.\d+)?)\s*(mg|mcg|g|μg|IU)\s*\)?$'

# Form qualifiers to normalize/remove for cleaner ingredient matching
FORM_QUALIFIERS = r'\b(extract|powder|root|leaf|fruit|capsule|tablet|softgel|liquid|oil|concentrate|supplement|formula|complex|blend|matrix)\b'

# Enhanced comma splitting pattern that respects nested parentheses and brackets
COMMA_SPLIT_PATTERN = r',(?![^()]*\))'

# Allergen-free patterns
ALLERGEN_FREE_PATTERNS = {
    "gluten": r"(gluten[\s-]*free|contains?\s+no\s+.*?gluten|does\s+not\s+contain\s+.*?gluten|wheat[\s-]*free)",
    "dairy": r"(dairy[\s-]*free|contains?\s+no\s+.*?(dairy|milk)|does\s+not\s+contain\s+.*?(dairy|milk))",
    "soy": r"(soy[\s-]*free|contains?\s+no\s+.*?soy|does\s+not\s+contain\s+.*?soy)",
    "nut": (
        r"((nut|tree[\s-]*nut)[\s-]*free|contains?\s+no\s+.*?nut|does\s+not\s+contain\s+.*?nut)"
    ),
    "egg": (
        r"(egg[\s-]*free|contains?\s+no\s+.*?egg|does\s+not\s+contain\s+.*?egg)"
    ),
    "shellfish": (
        r"(shellfish[\s-]*free|contains?\s+no\s+.*?shellfish|does\s+not\s+contain\s+.*?shellfish)"
    ),
    "peanut": (
        r"(peanut[\s-]*free|contains?\s+no\s+.*?peanut|does\s+not\s+contain\s+.*?peanut)"
    ),
    "yeast": r"(yeast[\s-]*free|contains?\s+no\s+.*?yeast|does\s+not\s+contain\s+.*?yeast)"
}

# Unsubstantiated claim patterns
UNSUBSTANTIATED_CLAIM_PATTERNS = [
    r"\bcure\b",
    r"\bmiracle\b",
    r"\bmagic\b",
    r"\bprevent\s+disease\b",
    r"\btreat\s+disease\b",
    r"\bheal\b",
    r"\b100%\s+effective\b",
    r"\bguaranteed\s+results\b"
]

# Natural source indicators
NATURAL_SOURCE_PATTERNS = [
    r"from\s+(organic\s+)?([a-zA-Z\s]+)",
    r"derived\s+from\s+([a-zA-Z\s]+)",
    r"natural\s+source",
    r"plant[\s-]*based",
    r"whole[\s-]*food"
]

# Standardization patterns
STANDARDIZATION_PATTERNS = [
    r"standardized\s+to\s+(\d+)%\s*([a-zA-Z\s]+)",
    r"(\d+)%\s+([a-zA-Z\s]+)\s+extract",
    r"containing\s+(\d+)%\s+([a-zA-Z\s]+)",
    r"extract\s+(\d+):\s*(\d+)",  # Extract ratios like "extract 4:1"
    r"(\d+):\s*(\d+)\s+extract",  # Ratios like "4:1 extract"
    r"concentrated\s+(\d+)x",     # Concentrated forms like "concentrated 10x"
    r"potency\s+guaranteed",      # Guaranteed potency
    r"standardized\s+extract",    # General standardized extract
    r"minimum\s+(\d+)%",          # Minimum percentages
    r"(\d+)\s*mg/g",             # Milligrams per gram ratios
    r"active\s+compounds?\s+(\d+)%", # Active compounds percentages
]

# Proprietary blend indicators
PROPRIETARY_BLEND_INDICATORS = [
    # Explicit proprietary terms
    "proprietary blend",
    "proprietary complex",
    "proprietary formula",
    "proprietary matrix",
    "exclusive blend",
    "exclusive formula",
    "patent-pending complex",
    "signature blend",
    # Generic blend indicators
    "blend",
    "matrix",
    "complex",
    "formula",
    "system",
    "stack",
    "mixture",
    "compound",
    # Common supplement blend types
    "powder blend",
    "extract blend",
    "herbal blend",
    "nutrient blend",
    "vitamin blend",
    "mineral blend",
    "enzyme blend",
    "probiotic blend",
    "amino blend",
    "protein blend",
    "botanical blend",
    "fruit blend",
    "vegetable blend",
    "greens blend",
    "antioxidant blend",
    "superfood blend"
]

# Enhanced delivery indicators
DELIVERY_ENHANCEMENT_PATTERNS = [
    r"liposomal",
    r"chelated",
    r"micronized",
    r"time[\s-]*release",
    r"sustained[\s-]*release",
    r"extended[\s-]*release",
    r"enhanced\s+absorption",
    r"bioenhanced"
]

# Clinical evidence patterns
CLINICAL_EVIDENCE_PATTERNS = [
    r"randomized.*controlled.*study",
    r"double[\s-]*blind.*study",
    r"placebo[\s-]*controlled.*study",
    r"clinical.*trial",
    r"clinical.*study",
    r"clinically.*studied",
    r"peer[\s-]*reviewed.*research",
    r"published.*research",
    r"scientific.*study",
    r"research.*study",
    r"university.*study",
    r"clinical.*research"
]

# Processing status codes
STATUS_SUCCESS = "success"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_INCOMPLETE = "incomplete"
STATUS_ERROR = "error"

# Default values
DEFAULT_SERVING_SIZE = 1
DEFAULT_DAILY_SERVINGS = 1
DEFAULT_STATUS = "active"

# Image URL template
DSLD_IMAGE_URL_TEMPLATE = "https://api.ods.od.nih.gov/dsld/s3/pdf/{}.pdf"

# Batch processing defaults
DEFAULT_BATCH_SIZE = 1000
DEFAULT_MAX_WORKERS = 4

# File extensions
VALID_INPUT_EXTENSIONS = [".json"]
OUTPUT_EXTENSION = ".jsonl"

# Processing thresholds and performance tuning
FUZZY_MATCHING_THRESHOLDS = {
    "fuzzy_threshold": 92,      # Primary fuzzy matching threshold (increased for safety)
    "partial_threshold": 95,    # Partial matching threshold (increased for safety)
    "minimum_fuzzy_length": 6,  # Minimum length for fuzzy matching (prevents short false matches)
    "context_window_size": 20,  # Characters around match for context validation
    "parallel_threshold": 10    # Minimum ingredients to use parallel processing
}

# Scoring system constants
SCORING_CONSTANTS = {
    # Quality bonuses
    "natural_bonus": 3,
    "premium_forms_threshold": 3,
    "super_combo_bonus_threshold": 3,
    "absorption_enhancement_points": 3,
    "organic_usda_verified_points": 3,
    "organic_general_points": 2,
    "synergy_minimum_ingredients": 2,
    "standardized_botanical_points": 2,

    # Quality thresholds
    "minimum_fuzzy_length": 8,  # For safe fuzzy matching
    "completeness_good_threshold": 90,
    "mapping_rate_good_threshold": 75,
    "unmapped_excellent_threshold": 5,

    # Clinical dosing adequacy
    "under_dosed_penalty": -2,
    "minimal_effective_penalty": 0,
    "optimal_dose_bonus": 2,
    "high_dose_bonus": 1,
    "excessive_dose_penalty": -1,

    # Industry benchmarking percentiles
    "industry_leader_percentile_min": 90,
    "industry_average_percentile": 50,
    "poor_performance_percentile_max": 25,

    # Product classification thresholds
    "premium_forms_super_combo_threshold": 3,
    "premium_forms_minimum_threshold": 2,
    "synergy_minimum_matched_ingredients": 2,
    "multivitamin_minimum_ingredients": 3,
    "high_priority_ingredient_threshold": 10,
    "safe_fuzzy_matching_minimum_length": 8
}

# Evidence and validation constants
EVIDENCE_SCORING = {
    "tier_1_score": 10,  # Very high evidence
    "tier_2_score": 7,   # High evidence
    "tier_3_score": 5,   # Moderate evidence
    "default_score": 3   # Low/unknown evidence
}

# Unit conversion aliases and mappings
UNIT_ALIASES = {
    "g": "gram",
    "mg": "milligram",
    "mcg": "microgram",
    "μg": "microgram",
    "iu": "IU",
    "kg": "kilogram",
    "oz": "ounce",
    "lb": "pound"
}

# Validation and processing thresholds
VALIDATION_THRESHOLDS = {
    "excellent_completeness": 90,    # 90%+ for excellent completion
    "good_completeness": 85,         # 85%+ for good completion
    "minimum_completeness": 70,      # 70%+ for minimum acceptable
    "excellent_success_rate": 95,    # 95%+ for excellent success
    "good_success_rate": 85,         # 85%+ for good success
    "minimum_success_rate": 70,      # 70%+ for minimum success
    "high_accuracy": 95,             # 95%+ for high accuracy
    "good_accuracy": 85,             # 85%+ for good accuracy
    "minimum_accuracy": 75,          # 75%+ for minimum accuracy
    "excellent_mapping": 90.0,       # 90%+ mapping rate for promotion
    "base_score_max": 80             # Maximum base score
}

# Logging format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

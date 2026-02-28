"""
Constants and configuration for DSLD data cleaning pipeline
"""
from pathlib import Path

# Base paths
# NOTE: Path resolution designed for portability - all paths relative to scripts/
BASE_DIR = Path(__file__).parent.parent     # Repository root
SCRIPTS_DIR = Path(__file__).parent          # scripts/ directory (where this file lives)
DATA_DIR = SCRIPTS_DIR / "data"              # scripts/data/ - reference databases
CONFIG_DIR = SCRIPTS_DIR / "config"          # scripts/config/ - pipeline configs
OUTPUT_DIR = SCRIPTS_DIR / "output"          # scripts/output/ - default output location
LOGS_DIR = SCRIPTS_DIR / "logs"              # scripts/logs/ - processing logs

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
OTHER_INGREDIENTS = DATA_DIR / "other_ingredients.json"  # Merged: non_harmful_additives + passive_inactive (FDA "Other Ingredients")
FUNCTIONAL_GROUPINGS = DATA_DIR / "functional_ingredient_groupings.json"  # Functional disclosure patterns & transparency scoring
BOTANICAL_INGREDIENTS = DATA_DIR / "botanical_ingredients.json"
INGREDIENT_CLASSIFICATION = DATA_DIR / "ingredient_classification.json"  # Hierarchical classification (source/summary/component) to prevent double-scoring
COLOR_INDICATORS = DATA_DIR / "color_indicators.json"  # Natural vs artificial color classification indicators
CLINICALLY_RELEVANT_STRAINS = (
    DATA_DIR / "clinically_relevant_strains.json"
)
CERT_CLAIM_RULES = DATA_DIR / "cert_claim_rules.json"  # Versioned rules for certification/claim detection with evidence-based scoring
UNIT_CONVERSIONS_DB = DATA_DIR / "unit_conversions.json"  # Nutrient + form specific unit conversions for dosage normalization

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
# NOTE: These are label math/rollups, not discrete scorable ingredients
EXCLUDED_NUTRITION_FACTS = {
    # Energy and macronutrients
    "calories", "energy", "kcal", "kcals", "cal", "total calories", "calories for fat",
    "total fat", "fat", "saturated fat", "trans fat", "polyunsaturated fat", "monounsaturated fat",
    "unsaturated fat", "saturated fatty acids", "unsaturated fatty acids",
    "total saturated fatty acids", "total unsaturated fatty acids",
    "polyunsaturated fatty acids", "monounsaturated fatty acids",
    "cholesterol", "total cholesterol", "dietary cholesterol",
    "total carbohydrates", "carbohydrates", "carbs", "total carbs", "total carb", "total carb.", "total carbohydrate",
    "net carbs", "net carbohydrates", "carbohydrate",
    "dietary fiber", "fiber", "soluble fiber", "insoluble fiber",
    "sugars", "total sugars", "added sugars", "sugar", "natural sugars",
    "sugar alcohols", "sugar alcohol", "polyols",
    "protein", "total protein", "proteins",
    "water", "moisture",
    # Common electrolytes/minerals when listed as basic nutrition facts
    "sodium", "salt", "sodium chloride",
    "chloride", "total chloride",
    # Other nutritional labels
    "serving size", "servings per container", "amount per serving",

    # Omega fatty acid totals (label rollups, not discrete ingredients)
    "total omega-3 fatty acids", "total omega-6 fatty acids", "total omega-9 fatty acids",
    "total omega-5 fatty acids", "total omega-7 fatty acids", "total omega-11 fatty acids",
    "total omega 3 fatty acids", "total omega 6 fatty acids", "total omega 9 fatty acids",
    "omega-6 fatty acids, total", "omega-9 fatty acids, total", "omega-3 fatty acids, total",
    "total omega-6", "total omega-9", "total omega-3",
    "total omega 3", "total omega 6", "total omega 9",
    "total omega-3s", "total omega 3s", "total omega-6s", "total omega 6s", "total omega-9s", "total omega 9s",
    "other omega-6 fatty acids", "other omega fatty acids", "other omegas", "other omega 3",
    "other omega-3s", "other omega 3s", "other omega-6s", "other omega 6s",
    "omega-5-6-7-8-9-11", "omega-6-7-9-11",
    "total omega 3-5-6-7-8-9-11", "total omega 3-5-6-7-9-11",
    "total omega 3-6-7-9-11", "total omega 3-6-9 fatty acids",
    "total omega-5 & 7 fatty acids", "total omega-5, 7 & 8 fatty acids",
    "total omega-5, 7 fatty acids", "total omega-9 & 11 fatty acids", "omega-6,9 fatty acids",
    "total omega oil", "total omega oils",

    # EPA/DHA totals (computed sums)
    "total epa + dha", "total epa/dha", "total dha, epa", "total dha plus epa",
    "epa+dha", "epa + dha", "total epa", "total dha",

    # Fish oil totals
    "total fish oil", "total fish oils", "total krill oil", "total fish oil concentrate",

    # Phospholipid totals
    "total phospholipids", "other phospholipids", "other soy phospholipids",

    # Tocotrienol/tocopherol totals
    "total tocotrienols", "total d-mixed tocotrienols", "total mixed tocotrienols",
    "total natural tocotrienols", "total natural d-mixed palm tocotrienols",

    # Individual saturated/monounsaturated fatty acids (nutrition fact components of oils, not supplements)
    "palmitic acid", "myristic acid", "stearic acid", "lauric acid",
    "caprylic acid", "capric acid", "caproic acid", "arachidic acid",
    "behenic acid", "lignoceric acid",
    "palmitoleic acid", "oleic acid", "gondoic acid", "erucic acid",
    # Omega category descriptors (rollup labels from nutrition panels, not discrete ingredients)
    "omega-3 polyunsaturated fat", "omega-3 polyunsaturated fats",
    "omega-6 polyunsaturated fat", "omega-6 polyunsaturated fats",
    "omega-9 monounsaturated fat", "omega-9 monounsaturated fats",
    "omega 6 fatty acids", "omega 7 fatty acids", "omega 9 fatty acids",
    "omega-9 fatty acid", "omega 9 fatty acid",
    "omegachoice omega-3 essential fatty acids",
    # Omega ethyl ester aggregates (nutrition totals, distinct from individual EE forms)
    "total omega-3 fatty acids ethyl esters", "total omega-3 fatty acid ethyl esters",
    "other omega-3 fatty acid ethyl ester", "other omega-3 fatty acids ethyl esters",
    "total omega-3 ethyl esters",
    # Generic botanical compound descriptors (label markers, not distinct ingredients)
    "pungent compounds",

    # Mineral component descriptors (listed as separate active but just a salt component)
    "sulfate", "sulfate ion",

    # Generic fiber descriptors (nutrition panel labels, not specific fibers)
    "dietary fibers",

    # Generic fatty acid aggregates
    "total fatty acids", "fatty acids and sterols", "fatty acids & sterols",
    "other fatty acids & phytonutrients", "other fatty acids and phytonutrients",
    "other omegas + fatty acids", "other beneficial fatty acids & nutrients",
    "free fatty acids", "esterified fatty acids",

    # Calorie/macro aggregates
    "total fats", "total sterols", "total amino acids", "total bioflavonoids",
    "total isoflavone", "total isoflavones", "total alkaloids", "total cannabinoids",
    "total collagen", "total omegas", "total caffeine",
    "total dihydroquercetins", "vitamin k activity from",

    # Pro-resolving mediator totals
    "total pro-resolving mediators", "pro-resolving mediators",
    "specialized pro resolving mediators", "spm",

    # Phytosterol totals
    "total phytosterol esters", "total phytosterols esters",

    # Additional omega variants
    "omega-5 fatty acids", "omega-7 fatty acids", "omega-11 fatty acids",
    "omega 3-6-9", "omega 3 fish oil",
    "total omega long-chain fatty acids", "total omega 3 polyunsaturates",
    "total omega 3-5-6-7-9", "omega-5,7 fatty acids",
    "dha and epa", "dha phospholipids", "epa phospholipids",

    # Fish oil aggregates
    "fish oils", "other fish oils", "fish body oils", "marine oil",
    "marine oils", "marine fish oil", "omega fatty acids",

    # Calorie/energy variants
    "grasa total",

    # Compound totals (aggregates, not discrete)
    "total docosapentaenoic acid", "total turmerones",
    "total eleutherosides", "total thiosulfinates",
    "total rosavins", "total ginsenosides",
    # Audit-derived descriptor/rollup rows leaking into scorable actives
    "total mixed tocopherols", "total tocopherols", "total mixed carotenoids",
    "total curcuminoids", "total gingerols", "total gingerols and shogaols",
    "contains zeaxanthin", "other omega-3 essential fatty acids",
    "other omega-3 fatty acids triglycerides", "other omega-3",
    "total omega-3 polyunsaturates", "total omega-3's", "total omega 3 fish oil",
    "total omega-3 long-chain fatty acids", "total omega-3 fatty acid",
    "total omega-3 fatty acids ethyl ester", "total astaxanthin",
    "total cbd", "total cannabidiol", "total non alpha tocopherol forms",
    "total active cla c18:2 conjugated", "total calamari oil",
    "total vitamin a", "total polyphenols",

    # Miscellaneous aggregates
    "other isomers", "other sterols",
    "other fatty acids, lignans", "other fatty acid ethyl ester",
    "five other naturally found fatty acids",
    "and five other naturally found fatty acids",
    # Descriptor-only blend headers observed in cleaned outputs
    "mineral enzyme activators",
    "ionic plant based minerals",
    "ionic plant-based minerals",
    "bioactive enzymes and proteins",
    "digestive aids and enzymes",
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
    "less than 2%:", "contains < 2%", "contains <2%", "contains < 2%:",
    "may also contain <2% of", "may also contain <2% of:",
    "may also contain < 2% of", "may also contain < 2% of:",

    # Other carbohydrate variations
    "other carbohydrates", "other carbohydrate", "other carbs",
    "net carbs", "net carbohydrates", "total carb", "total carb.",

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
    "ingredients",
    "contains", "includes", "consisting of", "also contains",

    # Invalid or placeholder values
    "none", "n/a", "not applicable", "null", "unknown",

    # Descriptive text that's not ingredients
    "naturally sweet", "energized nutrients",
    "acid reflux", "acid redux",

    # Quantity/composition descriptions
    "contains < 2% of", "contains 2% or less of the following",
    "may contain one or more of the following", "may contain one or more of the following:",
    "proprietary blend of",
    "from 800 mg of premium cultivar elderberries",
    "3.2 g (3,200 mg) of premium cultivar elderberries",
    "includes added sugar",
    "natural food base blend combination",
    # Nutritional macro fields (not ingredients)
    "net carbohydrate",
    # Dosage form artifacts (not ingredients)
    "tablets",
    # Elderberry serving-count descriptors (e.g. "50 Berries")
    "50 berries",
    "75 berries",
    "100 berries",
    # Dietary nitrate sub-labels (beet root context)
    "typical amino acid amounts (g)",
    "typical amino acid amounts (g) per serving",
    "typical amino acid profile",
    # Nutritional profile section headers (not ingredient names)
    "typical fatty acid profile",
    "fatty acid profile",
    "amino acid profile",
    "also containing additional carotenoids",
    "quath dravya of",
    "these three oils typically provide the following fatty acid profile",
    # Ayurvedic processing descriptors (label notes, not discrete ingredients)
    "processed by the method of siddha ghruta in",
    "processed by the method of siddha ghruta",
    "processed by siddha ghruta",
    # Parser artifacts observed in fresh Thorne/Nordic runs
    "from 250 mg dmsa",
    "from 100 mg dmsa",
    "25,000 iu from mixed carotenes",
    "and as (magnesium) citrate",
    "total cultures",
    # NOTE: "daltonmax 700" removed — DaltonMax 700 is a therapeutic 200:1 aloe vera concentrate (Pharmachem)
    "bio-enhanced",
    "bio enhanced",
    "mitoheal",
    # Audit-derived descriptor fragments leaking as ingredient rows
    "contains less than 0.5% of:",
    "contains less than 0.5% of",
    "contains less than 0.5% of the following:",
    "contains less than 0.5% of the following",
    # Alcohol solvent/carrier (not an active ingredient)
    "35% alcohol",
    "20% alcohol",
    "25% alcohol",
    "40% alcohol",
    "50% alcohol",
    # Generic blend/enzyme header descriptors
    "ionic minerals",
    "alkaline & neutral bacterial proteases",
    "providing",
    "providing:",
    "providing tocotrienols",
    "providing carvacrol",
    "carvacrol and thymol",
    "aromatase inhibition/estrogen modulation/dht block",
    "contains 12.5 mcg of stabilized allicin",
    # Fatty acid composition section headers (not discrete ingredients)
    "approximate fatty acid content",
    "approximate essential fatty acid (efa) content",
    "approximate essential fatty acid content",
    "fatty acid composition",
    "fatty acid content",
    "approximate fatty acid profile",
    # Omega aggregate totals (label-level summaries, not individual ingredients)
    "total omega-3, 6, 9 fatty acids",
    "total omega-3 6 9 fatty acids",
    "omega-3 6 9 fatty acids",
    # Category/marketing descriptors (not discrete ingredients)
    "microbial enzymes",
    "vitamin c support base",
    "organic alkalizing green juice powders",
    "male support",
    "female support",
    "immune support",
    "whole food and herb base",
    "stress & energy adaptogens",
    "cleansing & tonic support",
    "proprietary mix",
    # Inactive label phrases (not ingredients)
    "nothing else",
    "may contain one or both of the following",
    # Marketing/proprietary blend descriptors (not discrete ingredients)
    "immune factors",
    "farm fresh factors",
    # Branded blend/tablet technology descriptors (not discrete ingredients)
    "activessence",
    "solutab",
    # Inactive label descriptors / header leakage (not ingredients)
    "colour name",
    "anti-caking agent",
    "oral dissolve excipient",
    "vegetable culture",
    "enzyme digested",
    "enzyme pre-digested",
    "superpotency soyagen",
    "quik-sorb",
    # Label aggregate/descriptor phrases
    "total iodide/iodine",
    "total iodide iodine",
    "female support factors",
    "antioxidant response",
    # Skip phrases added for 7-9 occ tier remediation
    "organic aqua superfoods",
    "fermented botanicals",
    "vegetarian enzyme concentrate",
    "proprietary hcc",
    "glucodox amp activated protein kinase hormone booster",
    "male support factors",
    "a 4:1 proprietary extract",
    "a 5:1 proprietary extract",
    "a proprietary 10:1 water extract",
    "vitaveggie",
    "low-sodium concentrace(r)",
    "gentle digestive support",
    "active flavonols, flavonones, flavones & naringin",
    "100% pure optipure coral calcium",
    "passion factors",
    # Capsule/tablet section header artifacts (not discrete ingredients)
    "carotenoid mix",
    "enzymes",
    "sulfate",
    "digestive aids/enzymes",
    "bioactive enzymes & proteins",
    "co-nutrients",
    "co nutrients",
    "stomach",
    "whole food enzymes",
    "complete digestive support",
    "nitrate",
    "nitrates",
    # Standardization/marker descriptor rows (not standalone ingredients)
    "total silymarin",
    "macamides and macaenes",
    "80 mg broccoli",
    "8 mg cabbage",
    "40 mg broccoli",
    "3 mg cabbage",
    "50 mg carrots",
    "50 mg whole carrots",
    "240 mg whole oranges",
    "240 mg oranges",
    "proprietary mix of curcumin",
    # Softgels remediation: verified safe skip phrases (pure descriptors, zero ingredient identity)
    "which typically provides:",
    "providing minimum 40 mg of beta-sitosterol",
    "{less than or equal to} 40 mg beta-sitosterol",
    "40 mg beta-sitosterol",
    "containing fatty acids",
    "containing 24 mg of total rice tocotrienols",
    "provides 180 mg total polyphenols",
    "standardized to contain phosphatidylserine",
    "standardized to contain >4 mg of miliacin",
    "yielding 37 mg of trans resveratrol",
    "contains 15 mg of caffeine",
    "contains 2 mg of caffeine",
    "<1 mg of natural caffeine",
    "30 ppm scopoletin",
    "50% total menthol",
    "50% caffeine",
    "contains 2% or less",
    "contains 2% or less:",
    "excipients c.s.p.",
    "vitamin k activity",
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

# Required fields for RAW DSLD input validation (before cleaning transforms names)
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
SEVERITY_LEVELS = ["low", "moderate", "high", "critical"]

# DEPRECATED: Use SEVERITY_LEVELS directly. This alias exists only for backward compatibility.
RISK_LEVELS = SEVERITY_LEVELS

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

# DEPRECATED: Use data/cert_claim_rules.json instead for evidence-based certification detection
# These patterns are kept for backward compatibility but should be migrated to the rules database
# The new system provides: evidence objects, negative pattern validation, scope enforcement, feature gating
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

# DEPRECATED: Use data/cert_claim_rules.json (allergen_free_claims section) for evidence-based detection
# These patterns are kept for backward compatibility; the new system adds negative patterns and conflict checking
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

# NOTE: SCORING_CONSTANTS and EVIDENCE_SCORING were removed (dead code).
# All scoring values are now in config/scoring_config.json per "_important_rules": "config_driven".

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

# Validation and processing thresholds (for batch_processor.py, NOT scoring)
# NOTE: These are quality gates for pipeline validation, not scoring point values.
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

# Note: STATUS_* constants defined in "Processing status codes" section above (lines 427-430)
# Duplicate definition removed to avoid confusion

# Logging format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ==============================================================================
# SCORABLE INGREDIENT CLASSIFICATION CONSTANTS
# ==============================================================================
# Used by enrichment to separate therapeutic actives (scorable) from
# non-therapeutic label rows (excipients, headers, macro lines).

# Non-therapeutic parent blend names - ingredients nested under these
# should be skipped from quality scoring (Group A skip rule)
NON_THERAPEUTIC_PARENT_DENYLIST = {
    # Nutrition facts / macro lines
    "total carbohydrates", "total carbohydrate", "carbohydrates", "carbs",
    "sugars", "total sugars", "added sugars", "sugar",
    "calories", "energy", "kcal",
    "total fat", "fat", "saturated fat", "trans fat",
    "cholesterol", "dietary cholesterol",
    "protein", "total protein",
    "fiber", "dietary fiber",
    "sodium", "salt",
    # Other non-therapeutic parents
    "other carbohydrates", "other carbs",
    "sugar alcohols", "polyols",
    # Omega / fatty acid rollup parents (label math, not discrete actives)
    "omega-3 fatty acids", "omega-6 fatty acids", "omega-9 fatty acids",
    "omega 3 fatty acids", "omega 6 fatty acids", "omega 9 fatty acids",
    "total omega-3 fatty acids", "total omega-6 fatty acids", "total omega-9 fatty acids",
    "total omega 3 fatty acids", "total omega 6 fatty acids", "total omega 9 fatty acids",
    "omega fatty acids", "total fatty acids", "fatty acids",
    "total omegas", "total fish oil", "fish oil",
    "total omega oil", "total omega oils",
    "total omega-3s", "total omega 3s", "total omega-6s", "total omega 6s", "total omega-9s", "total omega 9s",
}

# Additive types that should be skipped from quality scoring
# These are excipients, not therapeutic ingredients
ADDITIVE_TYPES_SKIP_SCORING = {
    "sweetener", "sugar_alcohol", "polyol",
    "preservative", "preservative_natural", "preservative_synthetic",
    "processing_aid", "flow_agent", "anti_caking",
    "coating", "film_coating", "enteric_coating",
    "binder", "filler", "bulking_agent",
    "lubricant", "glidant",
    "colorant", "dye", "color_natural", "color_artificial",
    "flavor", "flavor_natural", "flavor_artificial",
    "solvent", "carrier",
    "emulsifier", "stabilizer", "thickener",
    "unspecified",  # Generic additive without therapeutic function
}

# HIGH-CONFIDENCE blend headers - skip even WITH dose present
# These are extremely unlikely to be actual therapeutic ingredients
BLEND_HEADER_PATTERNS_HIGH_CONFIDENCE = [
    # Proprietary prefix patterns - always headers regardless of what follows
    r"^proprietary\s+\w+\s*blend",  # "Proprietary X Blend", "Proprietary Cartilage Blend"
    r"^proprietary\s+blend",
    r"^proprietary\s+formula",
    r"^proprietary\s+complex",
    r"^proprietary\s+matrix",
    r"^proprietary\s+herbal",
    r"^general\s+proprietary",
    r"\bproprietary\b.*\bblend\b",  # catches prefixed names like "Brand Proprietary X Blend"
    r"\{blend\}",                   # Curly brace notation: {blend}
    r"^total\s+\{?blend\}?$",       # "Total Blend" or "Total {Blend}"
    # Label phrase headers that are never ingredients (P0 gummies audit fix)
    r"^contains\s+(less\s+than|<)\s*\d+\s*%",  # "Contains less than 2%", "Contains <2%"
    r"^contains\s+\d+\s*percent\s+or\s+less(\s+of)?",  # "Contains 2 percent or less of"
    r"^less\s+than\s+\d+\s*%",                 # "Less than 2% of"
    r"^<\s*\d+\s*%\s+of",                      # "<2% of"
    # Parser artifacts observed in Thorne/Nordic runs
    r"^from\s+\d+(?:,\d{3})?(?:\.\d+)?\s*mg\s+dmsa$",  # "from 250 mg DMSA"
    r"^\d+(?:,\d{3})?(?:\.\d+)?\s*iu\s+from\s+mixed\s+carotenes$",
    r"^and\s+as\s*\(magnesium\)\s*citrate$",
    r"^total\s+cultures$",
    r"^\s*min\.\s*\d+",
    r"^\s*providing\s+\d+",
    r"^\s*standardized\s+to\s+contain\s+\d+",
    r"\bblend\s*\(combination\)$",
    r"^bio[-\s]?enhanced$",
    r"^mitoheal$",
]

# Exact blend-header labels seen in DSLD where dose is blend total, not per-active dose.
BLEND_HEADER_EXACT_NAMES = {
    "acid comfort",
    "botaniplex",
    "natural defense blend",
    "superfood / immune support blends",
    # Gummies audit: branded blend headers that carry total weight, not per-active dose
    "smartypants probiotic blend",
    "omega fatty acid blend",
    "other omega-3 fatty acids",
    "other omega-6 fatty acids",
    "other omega fatty acids",
    "other omegas",
    # Parser/header artifacts from gummy and Thorne/Nordic outputs
    "mitoheal",
    "bio-enhanced",
    "bio enhanced",
    "from 250 mg dmsa",
    "from 100 mg dmsa",
    "25,000 iu from mixed carotenes",
    "and as (magnesium) citrate",
    "total cultures",
    "nordic flora woman blend (combination)",
    "5 billion probiotic blend",
    "proprietary blend of 9 strains of probiotic bacteria",
    "pure+ wild fish oil and antarctic krill (euphausia superba) oil concentrates",
    "pure wild fish oil and antarctic krill euphausia superba oil concentrates",
    # Softgels clean-stage unmapped high-frequency blend headers
    # NOTE: "zma" removed — ZMA sub-ingredients (zinc, magnesium, B6) should be scored individually
    "probiotic fermented culture",
    "probiotic fermented multi-culture",
    "probiotic fermented multi culture",
    "antioxidant boost",
    "vitality boost",
    "mineral enzyme activators",
    "ionic plant based minerals",
    "ionic plant-based minerals",
}

# LOW-CONFIDENCE blend headers - only skip if NO DOSE present
# These could match legitimate actives if they have a dose
BLEND_HEADER_PATTERNS_LOW_CONFIDENCE = [
    # Suffix patterns (only skip without dose)
    r"\bblends?$",      # "blend" or "blends" at end of name
    r"\bcomplex$",
    r"\bmatrix$",
    r"\bformulas?$",

    # Category-specific headers (only skip without dose)
    r"\bherbal\s+blend",
    r"\bbotanical\s+blend",
    r"\bprobiotic\b.*\bblend",
    r"\bprebiotic\b.*\bblend",
    r"\benzyme\s+blend",
    r"\bamino\b.*\bblend",
    r"\bvitamin\b.*\bblend",
    r"\bmineral\b.*\bblend",
    r"\bantioxidant\b.*\bblend",
    r"\bimmune\b.*\bblend",
    r"\benergy\b.*\bblend",
    r"\bsupport\b.*\bblend",
    r"\bdefense\b.*\bblend",
    r"\bsuperfood\b.*\bblend",
    r"\bomega\b.*\bblend",
    r"\bcartilage\b.*\bblend",
    r"\bfruit\b.*\bblend",
    r"\bvegetable\b.*\bblend",
    r"\bfoods?\b.*\bblend",
    r"\bextract\b.*\bblend",
    r"\bstrain\b.*\bblend",

    # Gummies-specific blend patterns (common blockers from audit)
    r"orchard\s+fruits?\b.*\bblend",        # "Orchard Fruits & Garden Veggies Powder Blend"
    r"garden\s+veggies?\b.*\bblend",
    r"powder\s+blend$",                      # Any "X Powder Blend"
    r"\bnatural\s+defense\b.*\bblend",       # "Natural Defense Blend"
    r"\bberry\b.*\bblend",                   # "Berry Blend", "Berry/Fruit Blend"
    r"\bsuper\s*fruits?\b.*\bblend",         # "Super Fruits Blend"
    r"\bgreens?\b.*\bblend",                 # "Greens Blend", "Green Blend"
    r"\bmushroom\b.*\bblend",                # "Mushroom Blend"
    r"\badaptogen\b.*\bblend",               # "Adaptogen Blend"
    r"\bpremium\b.*\bblend",                 # "Premium X Blend"
    r"\bfull[- ]?spectrum\b.*\bblend",       # "Full-Spectrum X Blend"
]

# Combined for backward compatibility (but prefer using the split lists)
BLEND_HEADER_PATTERNS = (
    BLEND_HEADER_PATTERNS_HIGH_CONFIDENCE +
    BLEND_HEADER_PATTERNS_LOW_CONFIDENCE
)

# Common excipients that should NEVER be promoted from inactive to scorable
# Even if they have a dose, these are not therapeutic
EXCIPIENT_NEVER_PROMOTE = {
    # Sweeteners
    "sorbitol", "xylitol", "mannitol", "erythritol", "maltitol", "isomalt",
    "d-xylose", "xylose",
    "stevia", "stevia extract", "stevia leaf extract", "stevia rebaudiana",
    "sucralose", "aspartame", "saccharin", "acesulfame", "acesulfame k",
    "honey", "sugar", "cane sugar", "organic cane sugar", "fructose",
    "glucose", "dextrose", "maltodextrin", "corn syrup",
    # Flavors
    "natural flavors", "natural flavor", "artificial flavors", "artificial flavor",
    "natural and artificial flavors", "flavor", "flavoring",
    # Carriers/fillers
    "gelatin", "vegetable gelatin", "pectin", "gum base",
    "cellulose", "microcrystalline cellulose", "cellulose gel",
    "silicon dioxide", "silica",
    "magnesium stearate", "stearic acid", "vegetable stearate",
    "rice flour", "rice bran", "rice powder",
    "dicalcium phosphate", "tricalcium phosphate",
    # Coatings
    "shellac", "carnauba wax", "beeswax", "pharmaceutical glaze",
    "hydroxypropyl methylcellulose", "hypromellose",
    # Preservatives
    "citric acid", "ascorbic acid preservative", "sorbic acid",
    "potassium sorbate", "sodium benzoate",
    # Processing aids
    "water", "purified water", "vegetable glycerin", "glycerin",
    "medium chain triglycerides", "mct oil",
    # Colorants (never therapeutic)
    "titanium dioxide", "caramel color", "annatto",
    "natural colors", "natural color", "natural coloring",
    "artificial colors", "artificial color",
    "food coloring", "vegetable juice color", "fruit juice color",
    "beta carotene color", "carmine", "fd&c colors",

    # Other common excipients
    "croscarmellose sodium", "croscarmellose", "sodium starch glycolate",
    "disodium edta", "edta",
    "potassium hydroxide", "sodium hydroxide",
    "lecithin", "soy lecithin", "sunflower lecithin",
    "non-gmo soy lecithin", "non gmo soy lecithin",

    # Sugar alcohols / polyols (catch generic group terms - singular AND plural)
    "sugar alcohol", "sugar alcohols",
    "polyol", "polyols",
    "sugar alcohols (polyols)", "sugar alcohol (polyol)",

    # Fiber excipients (structural, not therapeutic fiber supplements)
    # NOTE: "inulin fiber" removed - inulin can be therapeutic in fiber supplements
    # Handle inulin contextually (when in "Other ingredients" or gummy base)
    "vegetable fiber", "soluble corn fiber", "tapioca fiber",
    "organic tapioca fiber",

    # Processing aids / misc
    "directline technology",  # Brand-specific delivery system, not ingredient
    "fruit juice", "natural fruit juice", "fruit juice concentrate",
    # Proprietary blends, not specific ingredients
    "activessence", "quik-sorb",
    "trumask ultra liquid", "delete",

    # OILS/CARRIERS - Never therapeutic actives (from dev audit feedback)
    # These are carriers/processing aids even when listed in activeIngredients
    "sunflower oil", "sunflower seed oil", "organic sunflower oil",
    "coconut oil", "organic coconut oil", "fractionated coconut oil",
    "olive oil", "extra virgin olive oil",
    "safflower oil", "safflower seed oil",
    "soybean oil", "soy oil",
    "palm oil", "palm kernel oil",
    "canola oil", "rapeseed oil",
    "corn oil", "cottonseed oil",
    "sesame oil", "sesame seed oil",
    "vegetable oil", "mixed vegetable oils",
    "flaxseed oil", "linseed oil",  # As carrier, not omega supplement
    "avocado oil",
    "grape seed oil", "grapeseed oil",
    "rice bran oil",
    "almond oil", "sweet almond oil",
    "castor oil",
    "jojoba oil",

    # FOOD POWDERS - Non-bioactive forms (from dev audit feedback)
    # These are food ingredients, not therapeutic actives
    # NOTE: Even though some have IQM parents (dietary_nitrate, tart_cherry, cranberry,
    # pomegranate), juice powders are dilute food forms and scoring them as active
    # ingredients would pollute A1 scores. The IQM aliases exist for standardized
    # extracts, not generic juice powders used as food ingredients.
    "apple cider vinegar", "apple cider vinegar powder",
    "organic apple cider vinegar", "apple cider vinegar, powder",
    "beet root juice powder", "beet root juice, powder", "beet juice powder",
    "pomegranate fruit juice powder", "pomegranate fruit juice, powder",
    "pomegranate juice powder",
    "acai juice powder", "acai berry juice powder",
    "blueberry juice powder", "blueberry fruit juice powder",
    "cranberry juice powder", "cranberry fruit juice powder",
    "cherry juice powder", "tart cherry juice powder",

    # Generic food-as-ingredient patterns
    "fruit powder", "vegetable powder", "veggie powder",
    "whole food powder", "whole foods powder",
}

# Patterns for detecting non-therapeutic food ingredients
# These should be recognized but NOT scored as bioactive
NON_THERAPEUTIC_ACTIVE_PATTERNS = [
    r"^apple\s+cider\s+vinegar",
    r"\bjuice[,]?\s*powder$",
    r"^(sunflower|coconut|olive|safflower|soybean|palm|canola|corn)\s+oil$",
    r"\bcarrier\s+oil$",
    r"^organic\s+(sunflower|coconut|olive)\s+oil$",
]

# HIGH-SIGNAL potency markers - strong therapeutic indicators
# These patterns indicate a real therapeutic ingredient, not an excipient
POTENCY_MARKERS_HIGH_SIGNAL = [
    r"\d+\s*(mg|mcg|g|μg|iu)",    # Numeric dose with therapeutic unit
    r"\d+\s*%",                    # Percentage standardization
    r"\d+:\d+",                    # Extract ratio like 10:1, 4:1
    r"standardized\s+to",          # "Standardized to X%"
    r"\d+\s*cfu",                  # Probiotic CFU
    r"\d+\s*billion",              # Probiotic billions
    r"active\s+compound",          # "Active compound" language
]

# LOW-SIGNAL potency markers - need additional context to be therapeutic
# These alone are not sufficient for promotion (e.g., "vanilla extract" is flavor)
POTENCY_MARKERS_LOW_SIGNAL = [
    r"\bextract\b",                # Generic "extract" - needs context
    r"\bconcentrate\b",            # Could be therapeutic or flavor
]

# Skip reasons for tracking/debugging
SKIP_REASON_ADDITIVE = "is_additive"
SKIP_REASON_ADDITIVE_TYPE = "has_additive_type"
SKIP_REASON_NESTED_NON_THERAPEUTIC = "nested_under_non_therapeutic_parent"
SKIP_REASON_BLEND_HEADER_NO_DOSE = "blend_header_without_dosage"
SKIP_REASON_BLEND_HEADER_WITH_WEIGHT = "blend_header_total_weight_only"
SKIP_REASON_RECOGNIZED_NON_SCORABLE = "recognized_non_scorable"
SKIP_REASON_LABEL_PHRASE = "excluded_label_phrase"
SKIP_REASON_NUTRITION_FACT = "excluded_nutrition_fact"

# Promotion reasons for tracking/debugging
PROMOTE_REASON_KNOWN_DB = "known_therapeutic_db"
PROMOTE_REASON_HAS_DOSE = "has_measurable_dose"
PROMOTE_REASON_PRODUCT_TYPE_RESCUE = "product_type_rescue"
PROMOTE_REASON_ABSORPTION_ENHANCER = "absorption_enhancer_exception"

# Pseudo-units that should NOT be treated as valid dose units
# These appear in dirty data and should be treated as "no dose"
PSEUDO_UNITS_INVALID = {
    "serving", "servings", "scoop", "scoops", "capsule", "capsules",
    "tablet", "tablets", "softgel", "softgels", "gummy", "gummies",
    "lozenge", "lozenges", "drop", "drops", "spray", "sprays",
    "n/a", "na", "none", "unknown", "—", "-", "–", "",
    "piece", "pieces", "pack", "packs", "packet", "packets",
    "dose", "doses", "portion", "portions",
}

# Branded ingredient tokens that should be extracted from compound names
# These are proprietary/trademarked ingredient names that indicate specific forms
# When detected in a compound name like "KSM-66 Ashwagandha Root Extract",
# the branded token is extracted as the raw_source_text for quality map matching
BRANDED_INGREDIENT_TOKENS = {
    # Ashwagandha branded forms
    "ksm-66": "KSM-66",
    "ksm66": "KSM-66",
    "sensoril": "Sensoril",
    "shoden": "Shoden",
    # Curcumin branded forms
    "meriva": "Meriva",
    "longvida": "Longvida",
    "theracurmin": "Theracurmin",
    "bcm-95": "BCM-95",
    "curcuwin": "CurcuWin",
    "novasol": "NovaSol",
    # CoQ10 branded forms
    "ubiquinol": "Ubiquinol",
    "kaneka qh": "Kaneka QH",
    "kanekaqh": "Kaneka QH",
    # Magnesium branded forms
    "magtein": "Magtein",
    "albion": "Albion",
    "traacs": "TRAACS",
    # B vitamins branded forms
    "quatrefolic": "Quatrefolic",
    "methylfolate": "Methylfolate",
    "metafolin": "Metafolin",
    "mecobalactive": "MecobalActive",
    # Probiotics
    "lactobacillus gg": "Lactobacillus GG",
    "lg-gg": "LGG",
    "florastor": "Florastor",
    # Omega-3
    "superba": "Superba",
    "omegavia": "OmegaVia",
    "life's dha": "life's DHA",
    # Other common branded ingredients
    "cognizin": "Cognizin",
    "synapsa": "Synapsa",
    "suntheanine": "Suntheanine",
    "lactium": "Lactium",
    "setria": "Setria",
    "optizinc": "OptiZinc",
    "creapure": "Creapure",
    "carnosyn": "CarnoSyn",
    # Branded supplement ingredients (Wave 6)
    "nem": "NEM",
    "cerecalase": "CereCalase",
    "glucovantage": "GlucoVantage",
    "dynamine": "Dynamine",
    "astrazyme": "AstraZyme",
    "microbiomex": "MicrobiomeX",
    "carnipure": "Carnipure",
    "vegd3": "VegD3",
    "nitrosigine": "Nitrosigine",
    "neo-plex": "Neo-Plex",
    "furanomax": "FuranoMax",
    "gs4 plus": "GS4 Plus",
    "paractin": "ParActin",
    "silbinol": "Silbinol",
    "clear'saff": "Clear'Saff",
    "clearsaff": "Clear'Saff",
    "gutgard": "Gutgard",
    "glutalytic": "Glutalytic",
    "physioproteases": "pHysioProtease",
    "mycozyme": "Mycozyme",
    "soylife": "Soylife",
    "proanthodyn": "Proanthodyn",
    "oligonol": "Oligonol",
    "mitoburn": "MitoBurn",
    "ostivone": "Ostivone",
    "tamaflex": "TamaFlex",
    # Branded blends (no single parent mapping)
    "s7": "S7",
    "innoslim": "InnoSlim",
    "actisorb": "ActiSorb",
    "elevatp": "elevATP",
    "spectra": "Spectra",
    "source-70": "Source-70",
    "seditol": "Seditol",
    "ultra potent-c": "Ultra Potent-C",
    # Branded tokens added for 7-9 occ tier remediation
    "sod b extramel": "SOD B Extramel",
    "broccophane": "BroccoPhane",
    "vitacran": "VitaCran",
    "pteropure": "pTeroPure",
    "greengrown": "GreenGrown",
    "bacopin": "Bacopin",
    "hrg80": "HRG80",
    "biosorb": "BioSorb",
    "humulex": "Humulex",
    "bilberon": "Bilberon",
    "roseox": "RoseOx",
    "broccoraphanin": "BroccoRaphanin",
    "corowise": "Corowise",
    "sesaplex": "SesaPlex",
    "olivol": "Olivol",
    "tendoguard": "TendoGuard",
    "estrog-100": "EstroG-100",
    "vitaberry": "VitaBerry",
    "dermaval": "Dermaval",
    "biocore optimum complete": "BioCore Optimum Complete",
    "cynatine flx": "Cynatine FLX",
    # Branded tokens added for Softgels remediation
    "cardiokinase": "Cardiokinase",
    "bergacyn": "Bergacyn",
    "livinol": "Livinol",
    "opitac": "Opitac",
    "picroliv": "Picroliv",
    "onavita": "Onavita",
    "k-real": "K-REAL",
    "kreal": "K-REAL",
    "deltagold": "DeltaGold",
    "macarich": "MacaRich",
    "gojirich": "GojiRich",
    "acairich": "AcaiRich",
    "glucohelp": "GlucoHelp",
    "capsimax": "Capsimax",
    "maquibright": "MaquiBright",
    "curcu-gel": "Curcu-Gel",
    "allsure": "Allsure",
    "silexan": "Silexan",
    "mangoselect": "MangoSelect",
    "biosil": "BioSil",
    "ceralok": "CeraLOK",
    "ceratiq": "Ceratiq",
    "diosvein": "DiosVein",
    "sonova-400": "Sonova-400",
    "sabeet": "Sabeet",
    "oxystorm": "Oxystorm",
    "broccoplus": "BroccoPlus",
    "lalmin": "Lalmin",
    "bilberrix": "Bilberrix",
    "cardioaid-s": "CardioAid-S",
    "gg-gold": "GG-Gold",
    "cla80 femme": "CLA80 Femme",
    "nutri-nano": "Nutri-Nano",
    "ferronyl": "Ferronyl",
    "sun e 900": "Sun E 900",
    "folatine": "Folatine",
    "opti-3 choice": "OPTI-3 Choice",
    "elantria": "Elantria",
    "hiomega": "HiOmega",
    "bluerich": "BlueRich",
    # Life Extension branded ingredients
    "pycrinil": "Pycrinil",
    "coffeegenic": "CoffeeGenic",
    "koact": "KoAct",
    "neuravena": "Neuravena",
    "robuvit": "Robuvit",
    "enzogenol": "Enzogenol",
    "leucoselect": "LeucoSelect",
    "meganatural-bp": "MegaNatural-BP",
    "pepzingl": "PepZinGl",
    "osteoboron": "OsteoBoron",
    "fruitex b": "FruiteX-B",
    "xanthoforce": "XanthoForce",
    "xanthovital": "Xanthovital",
    "cinsulin": "CinSulin",
    "arginocarn": "ArginoCarn",
    "glycocarn": "GlycoCarn",
    "ironaid": "IronAid",
    "decursinol-50": "Decursinol-50",
    "clovinol": "Clovinol",
    "benegut": "Benegut",
    "activamp": "ActivAMP",
    "actiponin": "Actiponin",
    "integra-lean": "Integra-Lean",
    "ergoactive": "ErgoActive",
    "capsifen": "Capsifen",
    "fernblock": "FernBlock",
    "selenopure": "SelenoPure",
    "selenoexcell": "SelenoExcell",
    "crominex 3+": "Crominex 3+",
    "sibelius": "Sibelius",
    "metabolaid": "Metabolaid",
    "myoceram": "Myoceram",
    "zeropollution": "ZeroPollution",
    "tesnor": "Tesnor",
    "lipo-cmax": "Lipo-Cmax",
    "hmrlignan": "HMRlignan",
    "benolea": "Benolea",
    "origine 8": "Origine 8",
    "theanine xr": "Theanine XR",
    "delphinol": "Delphinol",
    "maritech 926": "Maritech 926",
    "lipowheat": "Lipowheat",
    "biovin": "BioVin",
    "sendara": "Sendara",
    "mirtogenol": "Mirtogenol",
    "picroprotect": "PicroProtect",
    "blueactiv": "BlueActiv",
    "bacognize ultra": "BaCognize Ultra",
    "rhuleave-k": "Rhuleave-K",
    "estro8pn": "Estro8PN",
    "alviolife": "AlvioLife",
    "ibsium": "ibSium",
    "lynside pro gi": "Lynside Pro GI",
    "masquelier's": "Masquelier's",
    "cytokine suppress": "Cytokine Suppress",
    "colostrinin": "Colostrinin",
    "insea2": "InSea2",
    "err 731": "ERr 731",
    # Pure Encapsulations branded tokens
    "tryptopure": "TryptoPure",
    "bergavit": "Bergavit",
    "zychrome": "Zychrome",
    "sirtmax": "Sirtmax",
    "preticx": "PreticX",
    "cereboost": "Cereboost",
    "serrazimes": "Serrazimes",
    "coffeeberry": "CoffeeBerry",
    "hyamax": "HyaMax",
    "mervia": "Mervia",
    "resvida": "resVida",
    "lustriva": "Lustriva",
    "phytopin": "PhytoPin",
    "mitopure": "Mitopure",
    "dnf-10": "DNF-10",
    "hytolive": "Hytolive",
    "n-zimes": "n-zimes",
    "c8vantage": "C8Vantage",
    "sunfiber": "Sunfiber",
    # Capsules branded tokens
    "senactiv": "Senactiv",
    "corebiome": "CoreBiome",
    "aquamin": "Aquamin",
    "cyplexinol": "Cyplexinol",
    "atpro": "ATPro",
    "laxosterone": "Laxosterone",
    "glisodin": "GliSODin",
    "macapure": "Macapure",
    "chromemate": "ChromeMate",
    "ceramide-pcd": "Ceramide-PCD",
    "zembrin": "Zembrin",
    "actazin": "Actazin",
    "oligopin": "Oligopin",
    "boswellin super": "Boswellin Super",
    "boswellin": "Boswellin",
    "tolerase g": "Tolerase G",
    "digezyme": "DigeZyme",
    "greenselect": "GreenSelect",
    "honopure": "HonoPure",
    "turmacin": "Turmacin",
    "peak02": "Peak02",
    "mobilee": "Mobilee",
    "cogniboost": "CogniBoost",
    "immunolin": "ImmunoLin",
    "emothion": "Emothion",
    "cocoabuterol": "Cocoabuterol",
    "richberry": "Richberry",
    "biocore dpp iv": "BioCore DPP IV",
    "leangbb": "LeanGBB",
    "lean gbb": "LeanGBB",
    "paradoxine": "Paradoxine",
    "dhqvital": "DHQVital",
    "ac-11": "AC-11",
}

# Deterministic serving unit normalization map
# Maps plural/variant forms to canonical singular form
# Used for dose normalization, RDA/UL per-day math, and UI display
SERVING_UNIT_NORMALIZATION_MAP = {
    # Capsules
    "capsules": "capsule",
    "capsule": "capsule",
    "caps": "capsule",
    "cap": "capsule",
    "vcaps": "capsule",
    "vcap": "capsule",
    "veggie capsule": "capsule",
    "veggie capsules": "capsule",
    "vegetable capsule": "capsule",
    "vegetable capsules": "capsule",
    "veg capsule": "capsule",
    "veg capsules": "capsule",
    # Tablets
    "tablets": "tablet",
    "tablet": "tablet",
    "tabs": "tablet",
    "tab": "tablet",
    "caplets": "caplet",
    "caplet": "caplet",
    # Softgels
    "softgels": "softgel",
    "softgel": "softgel",
    "soft gels": "softgel",
    "soft gel": "softgel",
    "liquid softgels": "softgel",
    "liquid softgel": "softgel",
    # Gummies
    "gummies": "gummy",
    "gummy": "gummy",
    "gummie": "gummy",
    "gummys": "gummy",
    "gummy bear": "gummy",
    "gummy bears": "gummy",
    # Lozenges
    "lozenges": "lozenge",
    "lozenge": "lozenge",
    # Drops
    "drops": "drop",
    "drop": "drop",
    "droppers": "dropper",
    "dropper": "dropper",
    "dropperfuls": "dropper",
    "dropperful": "dropper",
    # Scoops
    "scoops": "scoop",
    "scoop": "scoop",
    # Servings (meta-unit)
    "servings": "serving",
    "serving": "serving",
    # Packets/Sticks
    "packets": "packet",
    "packet": "packet",
    "sticks": "stick",
    "stick": "stick",
    "sachets": "sachet",
    "sachet": "sachet",
    # Sprays
    "sprays": "spray",
    "spray": "spray",
    "puffs": "puff",
    "puff": "puff",
    # Chews
    "chews": "chew",
    "chew": "chew",
    "chewables": "chewable",
    "chewable": "chewable",
    # Patches
    "patches": "patch",
    "patch": "patch",
    # Teaspoons/Tablespoons
    "teaspoons": "teaspoon",
    "teaspoon": "teaspoon",
    "tsp": "teaspoon",
    "tsps": "teaspoon",
    "tablespoons": "tablespoon",
    "tablespoon": "tablespoon",
    "tbsp": "tablespoon",
    "tbsps": "tablespoon",
    # Milliliters (for liquids)
    "ml": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "millilitre": "ml",
    "millilitres": "ml",
    # Ounces (for liquids)
    "oz": "oz",
    "ounce": "oz",
    "ounces": "oz",
    "fl oz": "fl oz",
    "fluid ounce": "fl oz",
    "fluid ounces": "fl oz",
}

# Absorption enhancers that may be promoted even without explicit dose
# These are therapeutically relevant for bioavailability, often hidden in "other ingredients"
# Promotion only with LOW confidence and when specifically flagged
ABSORPTION_ENHANCERS_PROMOTE_EXCEPTION = {
    # Piperine-based enhancers
    "piperine", "bioperine", "black pepper extract", "black pepper fruit extract",
    "piper nigrum", "piper nigrum extract",
    # Ginger-based enhancers
    "ginger extract", "ginger root extract", "zingiber officinale extract",
    # Lecithin-based (when therapeutic, not filler)
    # NOTE: Lecithin as generic filler stays in EXCIPIENT_NEVER_PROMOTE
    # Bromelain/proteolytic
    "bromelain", "papain", "proteolytic enzymes",
    # Fat-soluble vitamin enhancers
    "medium chain triglycerides therapeutic", "mct therapeutic",
}

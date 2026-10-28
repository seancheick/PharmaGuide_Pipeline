# What closes the 118 held source assessments — October 28, 2026

Source: `clinical_review_holds.csv` (rows in state `source_reconciled_required_holds_retained`) and the October 28 research response, which assigns the factual work to the agent and is not a new signature. Product counts overlap: one product can depend on several items.

| Group | Who closes it | Items | What is needed |
|---|---|---:|---|
| A. Missing fields in an already cited study | Agent | 22 | Read the cited study and fill the named fields (usually delivery form, dose, duration). |
| B. Cited studies with no recorded context yet | Agent | 15 | Read each listed study; record preparation, daily dose, population and outcomes, or record that it does not apply. |
| C. Full text needed for verified methods | Agent | 56 | Retrieve the full paper (many are paywalled) and record its verified methods; Dr Pham's existing decision then applies within its scope. |
| D. Exact contexts inside an existing signed scope | Agent | 14 | Record exact preparation/dose/population/outcome contexts that fit the scope she already signed. |
| E. Signed context to match to the exact product | Agent | 1 | Bind the signed context to the exact preparation and population. |
| F. Dr Pham acceptance | Dr Pham | 10 | One specific yes/no acceptance on a narrower claim; otherwise the signed limitation stays and no credit is given. |

## Items by group, most products first

### A. Missing fields in an already cited study

- **Vitamin D3** (`INGR_VITAMIN_D3`, 459 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Calcium** (`INGR_CALCIUM`, 289 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Coenzyme Q10** (`INGR_COQ10`, 241 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **L-Arginine** (`INGR_L_ARGININE`, 72 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **L-Carnitine** (`INGR_L_CARNITINE`, 71 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Beta-Alanine** (`INGR_BETA_ALANINE`, 68 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Resveratrol** (`PRECLIN_RESVERATROL`, 60 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Glucosamine Sulfate** (`INGR_GLUCOSAMINE_SULFATE`, 56 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Quercetin** (`INGR_QUERCETIN`, 49 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Valerian Root** (`INGR_VALERIAN`, 39 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Panax Ginseng** (`INGR_GINSENG`, 38 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Selenium** (`INGR_SELENIUM`, 35 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Inulin** (`INGR_INULIN`, 34 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Red Yeast Rice** (`INGR_RED_YEAST_RICE`, 28 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Huperzine A** (`PRECLIN_HUPERZINE_A`, 23 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Berberine** (`PRECLIN_BERBERINE_GENERIC`, 15 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Ceramides** (`INGR_CERAMIDES`, 13 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Beetroot (Dietary Nitrate)** (`INGR_BEETROOT`, 6 products): Extract missing fields from the cited study: included_studies.required_for_review_roles
- **Sulforaphane** (`PRECLIN_SULFORAPHANE`, 6 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Lactoferrin** (`INGR_LACTOFERRIN`, 5 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review
- **Theracurmin Curcumin** (`BRAND_THERACURMIN`, 4 products): Extract missing fields from the cited study: outcomes.review_incomplete
- **Zinc Carnosine** (`PRECLIN_ZINC_CARNOSINE`, 2 products): Extract missing fields from the cited study: dose.delivery_required_for_complete_review

### B. Cited studies with no recorded context yet

- **Protein Supplementation** (`INGR_WHEY_PROTEIN`, 415 products): Read cited studies 39303495 and record their preparation, dose, population and outcomes
- **Magnesium (Generic)** (`INGR_MAGNESIUM_GENERIC`, 242 products): Read cited studies 26752497,8792038 and record their preparation, dose, population and outcomes
- **Curcumin** (`INGR_TURMERIC`, 111 products): Read cited studies 38576215,38945354 and record their preparation, dose, population and outcomes
- **Branched Chain Amino Acids** (`INGR_BRANCHED_CHAIN_AMINO_ACIDS`, 103 products): Read cited studies 38241335 and record their preparation, dose, population and outcomes
- **Caffeine** (`INGR_CAFFEINE`, 92 products): Read cited studies 30926628,32551869,34139220 and record their preparation, dose, population and outcomes
- **L-Theanine** (`INGR_L_THEANINE`, 70 products): Read cited studies 24946991 and record their preparation, dose, population and outcomes
- **Green Tea Extract** (`INGR_GREEN_TEA`, 63 products): Read cited studies 19597519 and record their preparation, dose, population and outcomes
- **Elderberry Extract** (`INGR_ELDERBERRY`, 52 products): Read cited studies 30670267 and record their preparation, dose, population and outcomes
- **Acetyl-L-Carnitine** (`INGR_ACETYL_L_CARNITINE`, 40 products): Read cited studies 12598816,12804452,28349514,31201734 and record their preparation, dose, population and outcomes
- **Vitamin C** (`INGR_VITAMIN_C`, 37 products): Read cited studies 17636648,23440782 and record their preparation, dose, population and outcomes
- **Astaxanthin (Generic)** (`PRECLIN_ASTAXANTHIN_GENERIC`, 33 products): Read cited studies 32755613,35091276,38243785 and record their preparation, dose, population and outcomes
- **Inositol** (`INGR_INOSITOL`, 26 products): Read cited studies 35477841 and record their preparation, dose, population and outcomes
- **Berberine HCl** (`INGR_BERBERINE_HCL`, 25 products): Read cited studies 36999891 and record their preparation, dose, population and outcomes
- **Curcumin** (`PRECLIN_CURCUMIN_GENERIC`, 19 products): Read cited studies 38576215,38945354,39478418 and record their preparation, dose, population and outcomes
- **Zinc acetate/gluconate lozenges** (`INGR_ZINC_PICOLINATE`, 15 products): Read cited studies 27378206 and record their preparation, dose, population and outcomes

### C. Full text needed for verified methods

- **Biotin** (`INGR_BIOTIN`, 123 products): Get full text of 32762597 and record verified methods; then apply Dr Pham's existing scope
- **Ginger Root** (`INGR_GINGER`, 80 products): Get full text of 24642205,31937153 and record verified methods; then apply Dr Pham's existing scope
- **Milk Thistle (Silymarin)** (`INGR_MILK_THISTLE`, 80 products): Get full text of 17943794,38579127 and record verified methods; then apply Dr Pham's existing scope
- **Lactobacillus rhamnosus GG** (`STRAIN_LGG`, 78 products): Get full text of 26365389,26756877 and record verified methods; then apply Dr Pham's existing scope
- **Bromelain** (`INGR_BROMELAIN`, 75 products): Get full text of 37157782 and record verified methods; then apply Dr Pham's existing scope
- **Grape Seed Extract** (`INGR_GRAPE_SEED_EXTRACT`, 70 products): Get full text of 34798267 and record verified methods; then apply Dr Pham's existing scope
- **Vitamin B3 (Niacin)** (`INGR_VITAMIN_B3_NIACIN`, 65 products): Get full text of 11498460,15642562,25141367,9732910 and record verified methods; then apply Dr Pham's existing scope
- **L-Citrulline** (`INGR_L_CITRULLINE`, 64 products): Get full text of 30284051,33308806 and record verified methods; then apply Dr Pham's existing scope
- **Vitamin B6** (`INGR_VITAMIN_B6`, 53 products): Get full text of 10334745,36719452 and record verified methods; then apply Dr Pham's existing scope
- **Psyllium Husk** (`INGR_PSYLLIUM_HUSK`, 46 products): Get full text of 18985059,30239559 and record verified methods; then apply Dr Pham's existing scope
- **Chlorella** (`INGR_CHLORELLA`, 45 products): Get full text of 23234816,29037431,35331862 and record verified methods; then apply Dr Pham's existing scope
- **Spirulina** (`INGR_SPIRULINA`, 41 products): Get full text of 12487756,34538515,35988871,37263369,38401078 and record verified methods; then apply Dr Pham's existing scope
- **Taurine** (`INGR_TAURINE`, 41 products): Get full text of 32871172,41275513 and record verified methods; then apply Dr Pham's existing scope
- **Boswellia Serrata** (`PRECLIN_BOSWELLIA`, 38 products): Get full text of 32680575,35512759 and record verified methods; then apply Dr Pham's existing scope
- **Ashwagandha (Generic)** (`INGR_ASHWAGANDHA`, 37 products): Get full text of 36017529,39348746 and record verified methods; then apply Dr Pham's existing scope
- **Suntheanine** (`BRAND_SUNTHEANINE`, 36 products): Get full text of 22214254 and record verified methods; then apply Dr Pham's existing scope
- **Astragalus** (`INGR_ASTRAGALUS`, 33 products): Get full text of 37952511 and record verified methods; then apply Dr Pham's existing scope
- **Black Cohosh** (`INGR_BLACK_COHOSH`, 32 products): Get full text of 15565808,16039414,17565936 and record verified methods; then apply Dr Pham's existing scope
- **Chamomile Extract** (`INGR_CHAMOMILE`, 32 products): Get full text of 39106912 and record verified methods; then apply Dr Pham's existing scope
- **5-Hydroxytryptophan** (`INGR_5HTP`, 30 products): Get full text of 11869656,12169147 and record verified methods; then apply Dr Pham's existing scope
- **St. John's Wort** (`INGR_ST_JOHNS_WORT`, 30 products): Get full text of 18843608,28064110 and record verified methods; then apply Dr Pham's existing scope
- **Lemon Balm Extract** (`INGR_LEMON_BALM`, 28 products): Get full text of 34449930 and record verified methods; then apply Dr Pham's existing scope
- **Rhodiola Rosea** (`INGR_RHODIOLA`, 25 products): Get full text of 15256690 and record verified methods; then apply Dr Pham's existing scope
- **Iron Bisglycinate** (`INGR_IRON_BISGLYCINATE`, 23 products): Get full text of 36728680 and record verified methods; then apply Dr Pham's existing scope
- **Pyrroloquinoline Quinone** (`PRECLIN_PQQ`, 22 products): Get full text of 34415830 and record verified methods; then apply Dr Pham's existing scope
- **White Kidney Bean Extract** (`INGR_WHITE_KIDNEY_BEAN`, 20 products): Get full text of 42066439 and record verified methods; then apply Dr Pham's existing scope
- **Fenugreek Extract** (`INGR_FENUGREEK`, 19 products): Get full text of 32048383 and record verified methods; then apply Dr Pham's existing scope
- **Testofen Fenugreek** (`BRAND_TESTOFEN`, 18 products): Get full text of 21312304,26791805 and record verified methods; then apply Dr Pham's existing scope
- **Deglycyrrhizinated Licorice** (`PRECLIN_DGL`, 17 products): Get full text of 4933135 and record verified methods; then apply Dr Pham's existing scope
- **HMB (Beta-Hydroxy Beta-Methylbutyrate)** (`INGR_HMB`, 16 products): Get full text of 25700845,35911112,41305674 and record verified methods; then apply Dr Pham's existing scope
- **Pycnogenol** (`BRAND_PYCNOGENOL`, 15 products): Get full text of 18386255,31585179,31637782 and record verified methods; then apply Dr Pham's existing scope
- **Bitter Melon Extract** (`INGR_BITTER_MELON`, 15 products): Get full text of 30385422 and record verified methods; then apply Dr Pham's existing scope
- **Saccharomyces boulardii** (`STRAIN_SBOULARDII`, 14 products): Get full text of 26216624 and record verified methods; then apply Dr Pham's existing scope
- **Bacopa Monnieri** (`INGR_BACOPA`, 13 products): Get full text of 24252493,27912958 and record verified methods; then apply Dr Pham's existing scope
- **Kaneka Ubiquinol** (`BRAND_KANEKA_UBIQUINOL`, 12 products): Get full text of 16919858 and record verified methods; then apply Dr Pham's existing scope
- **Pantethine** (`INGR_PANTETHINE`, 12 products): Get full text of 21925346 and record verified methods; then apply Dr Pham's existing scope
- **Black Seed Oil (Nigella Sativa)** (`INGR_BLACK_SEED_OIL`, 11 products): Get full text of 21675032,37341696,40210172 and record verified methods; then apply Dr Pham's existing scope
- **L-5-Methyltetrahydrofolate** (`INGR_FOLATE_MTHF`, 11 products): Get full text of 16151461,16600937,25733468,25943647 and record verified methods; then apply Dr Pham's existing scope
- **Sea Buckthorn** (`INGR_SEA_BUCKTHORN`, 10 products): Get full text of 20554904,23472020,36043374 and record verified methods; then apply Dr Pham's existing scope
- **Artichoke Extract** (`PRECLIN_ARTICHOKE`, 8 products): Get full text of 14653829,18424099,22746542,28609140,34569671 and record verified methods; then apply Dr Pham's existing scope
- **Lutemax 2020** (`BRAND_LUTEMAX_2020`, 7 products): Get full text of 38890092 and record verified methods; then apply Dr Pham's existing scope
- **BioCell Collagen** (`BRAND_BIOCELL`, 6 products): Get full text of 22486722,31221944 and record verified methods; then apply Dr Pham's existing scope
- **Setria Glutathione** (`BRAND_SETRIA`, 6 products): Get full text of 24791752 and record verified methods; then apply Dr Pham's existing scope
- **Lion's Mane Mushroom** (`INGR_LION_MANE`, 6 products): Get full text of 18844328 and record verified methods; then apply Dr Pham's existing scope
- **Bifidobacterium animalis subsp. lactis BB-12** (`STRAIN_BB12`, 6 products): Get full text of 32059116 and record verified methods; then apply Dr Pham's existing scope
- **Berberine** (`INGR_BERBERINE`, 5 products): Get full text of 18442638,27157250 and record verified methods; then apply Dr Pham's existing scope
- **Saffron Extract** (`PRECLIN_SAFFRON`, 5 products): Get full text of 31135916,38913392,41693488 and record verified methods; then apply Dr Pham's existing scope
- **Affron Saffron Extract** (`BRAND_AFFRON`, 4 products): Get full text of 28735826,29510352,40414301 and record verified methods; then apply Dr Pham's existing scope
- **Niagen Nicotinamide Riboside** (`BRAND_NIAGEN`, 4 products): Get full text of 29992272 and record verified methods; then apply Dr Pham's existing scope
- **Shoden Ashwagandha** (`BRAND_SHODEN`, 4 products): Get full text of 32540634 and record verified methods; then apply Dr Pham's existing scope
- **Sytrinol** (`BRAND_SYTRINOL`, 4 products): Get full text of 17985810,25828621 and record verified methods; then apply Dr Pham's existing scope
- **Tesnor** (`BRAND_TESNOR`, 3 products): Get full text of 35129040 and record verified methods; then apply Dr Pham's existing scope
- **Quercetin Phytosome** (`PRECLIN_QUERCETIN_PHYTOSOME`, 3 products): Get full text of 40037045 and record verified methods; then apply Dr Pham's existing scope
- **Mitopure Urolithin A** (`BRAND_MITOPURE`, 2 products): Get full text of 32694802 and record verified methods; then apply Dr Pham's existing scope
- **PureWay-C** (`BRAND_PUREWAY_C`, 2 products): Get full text of 17901843,18971870 and record verified methods; then apply Dr Pham's existing scope
- **Carnipure L-Carnitine** (`BRAND_CARNIPURE`, 1 products): Get full text of 11788381,20045157 and record verified methods; then apply Dr Pham's existing scope

### D. Exact contexts inside an existing signed scope

- **Betaine Anhydrous** (`PRECLIN_BETAINE_ANHYDROUS`, 46 products): Record exact preparation/dose/population/outcome contexts inside Dr Pham's existing scope
- **Sensoril Ashwagandha** (`BRAND_SENSORIL`, 42 products): Record exact preparation/dose/population/outcome contexts inside Dr Pham's existing scope
- **Bilberry** (`INGR_BILBERRY`, 42 products): Record exact preparation/dose/population/outcome contexts inside Dr Pham's existing scope
- **KSM-66** (`BRAND_KSM66`, 28 products): Record exact preparation/dose/population/outcome contexts inside Dr Pham's existing scope
- **UC-II Undenatured Type II Collagen** (`BRAND_UCII`, 14 products): Record exact preparation/dose/population/outcome contexts inside Dr Pham's existing scope
- **Digestive Enzyme Complex** (`INGR_DIGESTIVE_ENZYMES`, 7 products): Record exact preparation/dose/population/outcome contexts inside Dr Pham's existing scope
- **Nitrosigine** (`BRAND_NITROSIGINE`, 5 products): Record exact preparation/dose/population/outcome contexts inside Dr Pham's existing scope
- **TamaFlex** (`BRAND_TAMAFLEX`, 5 products): Record exact preparation/dose/population/outcome contexts inside Dr Pham's existing scope
- **LactoSpore Bacillus Coagulans** (`BRAND_LACTOSPORE`, 4 products): Record exact preparation/dose/population/outcome contexts inside Dr Pham's existing scope
- **Sunfiber PHGG** (`BRAND_SUNFIBER`, 4 products): Record exact preparation/dose/population/outcome contexts inside Dr Pham's existing scope
- **AstaReal Astaxanthin** (`BRAND_ASTAREAL`, 3 products): Record exact preparation/dose/population/outcome contexts inside Dr Pham's existing scope
- **Relora** (`BRAND_RELORA`, 2 products): Record exact preparation/dose/population/outcome contexts inside Dr Pham's existing scope
- **LJ100 Tongkat Ali** (`BRAND_LJ100`, 1 products): Record exact preparation/dose/population/outcome contexts inside Dr Pham's existing scope
- **Zynamite** (`BRAND_ZYNAMITE`, 1 products): Record exact preparation/dose/population/outcome contexts inside Dr Pham's existing scope

### E. Signed context to match to the exact product

- **Cranberry Extract** (`INGR_CRANBERRY`, 131 products): Finish matching the signed context to exact preparation/population

### F. Dr Pham acceptance

- **Chondroitin Sulfate** (`INGR_CHONDROITIN_SULFATE`, 110 products): Facts extracted; needs acceptance of the exact preparation/regimen contexts
- **Potassium** (`INGR_POTASSIUM`, 107 products): Signed limitation kept; needs one specific acceptance answer only if a narrower claim should earn credit
- **Garlic Extract** (`INGR_GARLIC`, 97 products): Signed limitation kept; needs one specific acceptance answer only if a narrower claim should earn credit
- **Hydrolyzed Collagen Peptides** (`INGR_COLLAGEN_PEPTIDES`, 89 products): Signed limitation kept; needs one specific acceptance answer only if a narrower claim should earn credit
- **Plant Sterols/Stanols** (`INGR_PLANT_STEROLS`, 59 products): Signed limitation kept; needs one specific acceptance answer only if a narrower claim should earn credit
- **Echinacea** (`INGR_ECHINACEA`, 53 products): Facts extracted; needs acceptance of the exact preparation/regimen contexts
- **Cinnamon Extract** (`INGR_CINNAMON_EXTRACT`, 46 products): Signed limitation kept; needs one specific acceptance answer only if a narrower claim should earn credit
- **Gamma-Aminobutyric Acid (GABA)** (`INGR_GABA`, 45 products): Signed limitation kept; needs one specific acceptance answer only if a narrower claim should earn credit
- **Omega-3 Fatty Acids** (`INGR_OMEGA3`, 36 products): Signed limitation kept; needs one specific acceptance answer only if a narrower claim should earn credit
- **Cordyceps Mushroom** (`PRECLIN_CORDYCEPS`, 5 products): Facts extracted; needs acceptance of the exact preparation/regimen contexts

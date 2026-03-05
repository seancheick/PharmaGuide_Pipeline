import json

# Load Emerald
with open('scripts/output_Emerald-Labs-2-17-26-L88/cleaned/cleaned_batch_1.json') as f:
    emerald = json.load(f)

# Collagen check
collagen_products = []
uc_ii_products = []
for i, product in enumerate(emerald[:50]):
    for ing in product.get('active_ingredients', {}).get('ingredients', []):
        name = ing.get('name', '').lower()
        if 'collagen type ii' in name:
            collagen_products.append((product.get('product_name'), ing['name']))
        elif 'uc-ii' in name:
            uc_ii_products.append((product.get('product_name'), ing['name']))

print("Collagen Type II found in products:")
for pname, ing_name in collagen_products[:2]:
    print(f"  {pname}: {ing_name}")

print("\nUC-II found in products:")
for pname, ing_name in uc_ii_products[:2]:
    print(f"  {pname}: {ing_name}")

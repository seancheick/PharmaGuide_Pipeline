#!/usr/bin/env python3
"""
DSLD Unmapped Ingredient Audit
"""
import json
import sys

# Load Emerald data
with open('scripts/output_Emerald-Labs-2-17-26-L88/cleaned/cleaned_batch_1.json') as f:
    emerald = json.load(f)

# Load Hum data
with open('scripts/output_Hum-2-17-26-L23/cleaned/cleaned_batch_1.json') as f:
    hum = json.load(f)

print("=" * 70)
print("DSLD UNMAPPED INGREDIENT AUDIT")
print("=" * 70)

# Find collagen products in Emerald
print("\n1. COLLAGEN ENTRIES (Emerald Labs)")
print("-" * 70)
found = False
for i, product in enumerate(emerald):
    active = product.get('active_ingredients', {}).get('ingredients', [])
    for ing in active:
        if 'collagen' in ing.get('name', '').lower():
            print(f"Product #{i}: {product.get('product_name', 'N/A')}")
            print(f"  → Active Ingredient: '{ing['name']}'")
            print(f"  → Details: {ing}")
            found = True
            break
    if found:
        break

# Find UC-II products
print("\n2. UC-II ENTRIES (Emerald Labs)")
print("-" * 70)
found = False
for i, product in enumerate(emerald):
    active = product.get('active_ingredients', {}).get('ingredients', [])
    for ing in active:
        if 'uc-ii' in ing.get('name', '').lower():
            print(f"Product #{i}: {product.get('product_name', 'N/A')}")
            print(f"  → Active Ingredient: '{ing['name']}'")
            found = True
            break
    if found:
        break

# Check Vegetable Capsule classification
print("\n3. VEGETABLE CAPSULE ENTRIES (both brands)")
print("-" * 70)
emerald_capsule = 0
for product in emerald:
    inactive = product.get('inactive_ingredients', {}).get('ingredients', [])
    for ing in inactive:
        if 'vegetable capsule' in ing.get('name', '').lower():
            emerald_capsule += 1
            break

hum_capsule = 0
for product in hum:
    inactive = product.get('inactive_ingredients', {}).get('ingredients', [])
    for ing in inactive:
        if 'vegetable capsule' in ing.get('name', '').lower():
            hum_capsule += 1
            break

print(f"Emerald Labs: {emerald_capsule} products contain 'Vegetable Capsule' (inactive)")
print(f"Hum: {hum_capsule} products contain 'Vegetable Capsule' (inactive)")

# Check Coconut Palm Sugar
print("\n4. COCONUT PALM SUGAR (Hum)")
print("-" * 70)
found = False
for i, product in enumerate(hum):
    inactive = product.get('inactive_ingredients', {}).get('ingredients', [])
    for ing in inactive:
        if 'coconut' in ing.get('name', '').lower() and 'sugar' in ing.get('name', '').lower():
            print(f"Product #{i}: {product.get('product_name', 'N/A')}")
            print(f"  → Inactive Ingredient: '{ing['name']}'")
            found = True
            break
    if found:
        break

print("\n" + "=" * 70)

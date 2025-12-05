"""Check RECIPES structure"""
from collections import Counter
import re

with open('data/recipes.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all calorie ranges
cal_ranges = re.findall(r'^\s+(\d{4}):\s*\{', content, re.MULTILINE)

counts = Counter(cal_ranges)

print("Calorie ranges and their occurrences:")
for cal in sorted(set(cal_ranges)):
    print(f"  {cal}: {counts[cal]} entry/entries")

print("\nChecking for 1900...")
if '1900' in cal_ranges:
    print("  ✓ 1900 found")
else:
    print("  ✗ 1900 NOT found")

print("\nIssues found:")
issues = []
for cal in ['1700', '1800', '2000', '2100']:
    if counts[cal] == 1:
        issues.append(f"  - {cal} has only 1 day (should have 14)")

if '1900' not in cal_ranges:
    issues.append(f"  - 1900 is missing completely")

if issues:
    for issue in issues:
        print(issue)
else:
    print("  None!")

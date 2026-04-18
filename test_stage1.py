import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

from parser import parse_csv_stage1

FILE_PATH   = r".\projects\Project_A\raw\manual qpr_2020.csv"
CONFIG_PATH = r".\projects\Project_A\config.json"

with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

rows, warnings = parse_csv_stage1(FILE_PATH, CONFIG)

print("=" * 60)
print(f"[1] 총 row 수: {len(rows)}")

print("=" * 60)
print(f"[2] Warnings ({len(warnings)}개):")
if warnings:
    for w in warnings:
        print(f"  {w}")
else:
    print("  없음")

print("=" * 60)
print(f"[3] 첫 3개 row:")
for i, row in enumerate(rows[:3], start=1):
    print(f"\n  --- Row {i} ---")
    for k, v in row.items():
        print(f"  {k}: {v!r}")

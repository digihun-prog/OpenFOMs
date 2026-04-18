import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

from parser import parse_csv_stage1, group_rows_by_key, select_main_row
from validators import is_main_row

FILE_PATH   = r".\projects\Project_A\raw\manual qpr_2020.csv"
CONFIG_PATH = r".\projects\Project_A\config.json"

with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

# Stage 1
rows, warnings = parse_csv_stage1(FILE_PATH, CONFIG)

print("=" * 60)
print(f"[Stage 1] 총 row 수: {len(rows)}")
if warnings:
    for w in warnings:
        print(f"  WARNING: {w}")

# 원본 행 위치 주입 (1-based, 헤더 제외)
for idx, row in enumerate(rows, start=2):
    row["_row_index"] = idx

# Stage 2 - Grouping
grouped = group_rows_by_key(rows, CONFIG)

print("=" * 60)
print(f"[Stage 2] 전체 그룹 수: {len(grouped)}")
print("=" * 60)

plan_col   = CONFIG["plan_qty_col"]
actual_col = CONFIG["actual_qty_col"]

for i, (key, group_rows) in enumerate(grouped.items()):
    if i >= 5:
        break

    main_rows = [
        r for r in group_rows
        if is_main_row(r.get(plan_col), r.get(actual_col))
    ]
    main_row, sel_warnings = select_main_row(group_rows, CONFIG, key_repr=repr(key))

    print(f"\n--- Group {i + 1} ---")
    print(f"  Key           : {repr(key)}")
    print(f"  Row 개수      : {len(group_rows)}")
    print(f"  Main Row 존재 : {main_row is not None}")
    print(f"  Main Row 수   : {len(main_rows)}")
    if sel_warnings:
        for w in sel_warnings:
            print(f"  WARNING: {w}")

    if len(main_rows) >= 2:
        print(f"  [중복 Main Row 상세]")
        for j, mr in enumerate(main_rows, start=1):
            print(f"    -- Main Row {j} (행 {mr.get('_row_index', '?')}) --")

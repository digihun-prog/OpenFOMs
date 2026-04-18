import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

from parser import parse_csv_stage1, group_rows_by_key, build_parsed_records

FILE_PATH   = r"D:\OpenFOMs\projects\Project_A\raw\manual qpr_2020.csv"
CONFIG_PATH = r"D:\OpenFOMs\projects\Project_A\config.json"

with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

# Stage 1
rows, stage1_warnings = parse_csv_stage1(FILE_PATH, CONFIG)

# Stage 2
grouped = group_rows_by_key(rows, CONFIG)

# Stage 3
result = build_parsed_records(grouped, CONFIG)

print("=" * 60)
print(f"[1] 총 ParsedRecord 수: {len(result.records)}")

print("=" * 60)
print(f"[2] 전체 warnings 수: {len(result.warnings)}")
for w in result.warnings:
    print(f"  {w}")

print("=" * 60)
print(f"[3] 첫 3개 ParsedRecord 상세:")

for i, rec in enumerate(result.records[:3], start=1):
    print(f"\n{'=' * 60}")
    print(f"  Record {i}")
    print(f"  Key             : {repr(rec.key)}")
    print(f"  plan_qty        : {rec.plan_qty}")
    print(f"  actual_qty      : {rec.actual_qty}")
    print(f"  work_time       : {rec.work_time}")
    print(f"  cycle_time      : {rec.cycle_time}")
    print(f"  downtime  건수  : {len(rec.downtime_items)}")
    print(f"  nonconformity 건수: {len(rec.nonconformity_items)}")
    print(f"  defect    건수  : {len(rec.defect_items)}")
    if rec.warnings:
        print(f"  warnings:")
        for w in rec.warnings:
            print(f"    {w}")

    if i == 1:
        print(f"\n  [첫 Record 원인 상세]")

        print(f"  -- downtime_items (최대 3개) --")
        for item in rec.downtime_items[:3]:
            print(f"    cause={item.cause!r}, duration={item.duration}, row_index={item.row_index}")

        print(f"  -- nonconformity_items (최대 3개) --")
        for item in rec.nonconformity_items[:3]:
            print(f"    cause={item.cause!r}, qty={item.qty}, row_index={item.row_index}")

        print(f"  -- defect_items (최대 3개) --")
        for item in rec.defect_items[:3]:
            print(f"    cause={item.cause!r}, qty={item.qty}, row_index={item.row_index}")

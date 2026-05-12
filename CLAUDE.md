# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run backend pipeline tests (use Project_A data)
python test_stage1.py   # CSV load + normalize
python test_stage2.py   # Row grouping by composite key
python test_stage3.py   # ParsedRecord + factor accumulation

# Launch Assist GUI
python Assist/main.py

# Run Bridge CLI (WIP normalizer)
python Bridge/main.py <input_xlsx_or_dir> -o <output_dir> [--recursive] [--no-subtotals]
```

No build step required. All code is plain Python; dependencies are `PySide6`, `openpyxl`, and optionally `xlrd` (for `.xls`).

## Reference Documents

Before implementing anything, read in this order based on the task:

| Document | When to read |
|----------|-------------|
| `FOM_RULES.md` | Any task — top-level technical spec (File Set, data flow, MCP, security) |
| `QPR_RULES.md` | QPR file structure, parsing logic, DB loading |
| `ASSIST_RULES.md` | Assist GUI, column mapping rules, config.json generation |
| `CLAUDE.md` (this file) | Code architecture, module locations |

## Architecture

### System Overview

Three layers share a common QPR data model but are loosely coupled:

```
Source data (CSV / Excel)
        ↓
   Assist GUI          Bridge CLI (WIP only)
        ↓                      ↓
  mapping_rules.json    normalized long-format CSV
        ↓
  config.json  ←── parser-consumable column mappings
        ↓
  parser.py / validators.py / models.py  (core backend)
        ↓
  db.py  (SQLite: TB_PRODUCTION + 3 factor tables + TB_WARNING)
```

### QPR Data Model (QPR_RULES.md)

A **work unit** = one composite key group. Each group contains:
- **Main Row** (exactly 1): has `실적수량` or `계획수량`
- **Detail Rows** (0+): factor records (비가동 / 부적합 / 불량)

The composite key is 8 fields: `일자, Shift, 대분류, 중분류, 소분류, 설비, 제품, 작업자`.  
`process_hierarchy` (대분류/중분류/소분류) meaning varies per project — never assume fixed domain labels.

**Terminology**: Korean UI text uses **요인** (factor) for 비가동/부적합/불량. English identifiers still use `cause` (`CauseMapping`, `cause_src`, `CAUSE_COLUMNS`, etc.).

### Core Backend (root-level)

- **parser.py** — `load_csv_rows()` (UTF-8/EUC-KR auto-detect) → `group_rows_by_key()` → `select_main_row()` → `build_parsed_records()`
- **validators.py** — `normalize_row()`, `clean_value()` (empty→None), safe `to_float()/to_int()`
- **models.py** — `QPRKey`, `ParsedRecord`, `ParseResult`, and three factor item types (`DowntimeItem`, `NonconformityItem`, `DefectItem`)
- **db.py** — SQLite schema; call `init_db()` before any inserts. Tables: `TB_PRODUCTION`, `TB_DOWNTIME`, `TB_NONCONFORMITY`, `TB_DEFECT`, `TB_WARNING`. `TB_PRODUCTION` stores `process_level1/2/3` for the hierarchy.

### Assist Subsystem (`Assist/`)

GUI tool that maps arbitrary source columns to the 19 QPR standard columns.

**Key objects and their roles:**

| File | Role |
|------|------|
| `models/mapping_rule.py` | `MappingMode` enum (COLUMN/DEFAULT/BLANK), `MappingRule`, `CausePairMapping`, `CauseMapping` |
| `models/qpr_schema.py` | `QPR_COLUMNS` (order matters), `MANDATORY_COLUMNS`, `CAUSE_COLUMNS`, `CAUSE_PAIRS`, `COLUMN_DEFAULTS` |
| `models/project_config.py` | `ProjectConfig` dataclass — holds `rules` + `cause_mapping` |
| `services/mapping_service.py` | `make_default_ruleset()`, `auto_match()`, `validate()`, `validation_summary()` |
| `services/project_store.py` | Reads/writes `mapping_rules.json` v2 and `config.json` (parser-consumable) |
| `services/qpr_builder.py` | `MappingRuleSet` + `CauseMapping` → QPR rows; 1-to-N row expansion |
| `services/file_loader.py` | Loads CSV/XLSX/XLS; stores last `delimiter` on `self.delimiter` |
| `ui/mapping_view.py` | Two `QScrollArea` panels + `LineArea` (custom `paintEvent` connector lines) |

**Two distinct JSON files per project:**
- `mapping_rules.json` v2 — Assist-internal. Non-factor 13 columns in `rules`; factor 6 columns in `cause_mapping` (blank-forced in `rules`).
- `config.json` — Parser-consumable format (`date_col`, `machine_col`, `process_hierarchy[]`, …). Structure must match `projects/Project_A/config.json` exactly.

**`cause_mapping` structure** (`mapping_rules.json` v2):
```json
{
  "version": 2,
  "rules": { "...13 non-factor columns..." },
  "cause_mapping": {
    "downtime":      [{"cause_src": "비가동요인1", "qty_src": "비가동시간1"}, ...],
    "nonconformity": [{"cause_src": "부적합요인1", "qty_src": "부적합수량1"}],
    "defect":        []
  }
}
```
v1 files (no version key) are auto-migrated to a single-slot `CauseMapping` on load.

**Multi-slot factor expansion** (`qpr_builder.py`):  
`QPRBuilder.build()` has two paths:
- **Path A** (`cause_mapping` present & non-empty): `_expand_source_row()` — Slot 0 → Main Row; Slots 1+ → new Detail Rows containing only the 8 key columns + that factor pair (all qty/production columns blank).
- **Path B** (legacy, no `cause_mapping`): `_resolve_row()` — 1-to-1 source→QPR row transformation.

**`__copy_actual__` sentinel**: When `계획수량` rule is `DEFAULT/__copy_actual__`, `project_store.save_config()` resolves it to the source column name of `실적수량`.

**MANDATORY_COLUMNS** (QPR 생성 최소 필수): `일자, 설비, 제품, 작업자, 실적수량`. 나머지는 DEFAULT 또는 BLANK 허용.

**`_QPR_TO_CONFIG_KEY` in `project_store.py`**: The authoritative mapping from QPR column names → config.json keys. `None` values collect into `process_hierarchy[]` in order (대분류→[0], 중분류→[1], 소분류→[2]).

**`config.json` key contract** (18 keys; must match `projects/Project_A/config.json`):
`delimiter`, `date_col`, `shift_col`, `process_hierarchy` (list), `machine_col`, `product_col`, `worker_col`, `plan_qty_col`, `actual_qty_col`, `work_time_col`, `efficiency_col`, `cycle_time_col`, `downtime_col`, `downtime_time_col`, `nonconformity_col`, `nonconformity_qty_col`, `defect_col`, `defect_qty_col`

**MappingView UI architecture** (`ui/mapping_view.py`):  
Replaced QGraphicsScene/QGraphicsProxyWidget with plain widgets inside two `QScrollArea` panels:
- Left `QScrollArea` → `SourceColumnWidget` items
- `LineArea` (custom `paintEvent`) → draws connector lines using `mapToGlobal`/`mapFromGlobal` so scroll position is always accounted for
- Right `QScrollArea` → `QPRColumnWidget` items + `CauseGroupPanel` for each of the 3 factor types

**LineArea visual states** (ASSIST_RULES.md §10):
- COLUMN mapping → 파란 실선
- DEFAULT mapping → 회색 점선
- BLANK → 선 없음
- Factor cause slot → 주황 파선 / factor qty slot → 주황 점선 (더 가늘게)
- 필수 누락 → 빨간 강조 / 정상 완료 → 초록 표시

`CauseGroupPanel` slots are added/removed dynamically. Factor qty columns (`비가동시간`, `부적합수량`, `불량수량`) are not shown as standalone rows; they live inside the panel's slot combos.

### Bridge Subsystem (`Bridge/`)

Standalone CLI for normalizing "재공조회" WIP Excel files. Not integrated into the core parser/DB flow yet.

**Data model** (`Bridge/models/schema.py`): `WipRecord` (33 fields: snapshot_date, vendor, device_code, 13 process-stage columns, stock/balance quantities, row_hash, metadata). `ValidationIssue` and `RunSummary` for reporting.

**Column config** (`Bridge/config/column_map.py`): `COLUMN_MAP` — 29 canonical field names with possible raw header variants (handles OCR/spelling variations). `PROCESS_COLS` list; `INT_COLS` for numeric parsing.

**Pipeline** (`Bridge/services/runner.py`): `file_finder` → `sheet_reader` (expand merged cells) → `header_mapper` (detect anchor row by "업체"+"DEVICE" keywords) → `row_processor` (forward-fill vendor, parse ints, compute `row_hash`) → `validator` → `output_writer`

Input filename pattern: `재공조회_YYMMDD.xlsx`. Sheet name pattern: `M.DD`.

### Project Workspaces (`projects/`)

**Scope rule**: Only `projects/Project_A/` is the reference project for analysis and tests. All other subdirectories under `projects/` are personal test workspaces — do not analyze, reference, or expose their contents or names.

**Privacy rule**: This is an open-source project. Never mention or expose specific company or client names that may appear in project folder names or data files.

`projects/Project_A/` structure (reference only):
- `config.json` — parser-consumable (hand-authored; reference structure for all auto-generated configs)
- `mapping_rules.json` — Assist-managed
- `output/` — QPR CSV outputs from Assist
- `raw/` — source data

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

# Run Bridge CLI (Lumicom WIP normalizer)
python Bridge/main.py <input_xlsx_or_dir> -o <output_dir> [--recursive] [--no-subtotals]
```

No build step required. All code is plain Python; dependencies are `PySide6`, `openpyxl`, and optionally `xlrd` (for `.xls`).

## Architecture

### System Overview

Three layers share a common QPR data model but are loosely coupled:

```
Source data (CSV / Excel)
        ↓
   Assist GUI          Bridge CLI (Lumicom WIP only)
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
- **models.py** — `QPRKey`, `ParsedRecord`, `ParseResult`, and three factor item types
- **db.py** — SQLite schema; call `init_db()` before any inserts

### Assist Subsystem (`Assist/`)

GUI tool that maps arbitrary source columns to the 19 QPR standard columns.

**Key objects and their roles:**

| File | Role |
|------|------|
| `models/mapping_rule.py` | `MappingMode` enum (COLUMN/DEFAULT/BLANK), `MappingRule`, `CausePairMapping`, `CauseMapping` |
| `models/qpr_schema.py` | `QPR_COLUMNS` (order matters), `MANDATORY_COLUMNS`, `CAUSE_COLUMNS`, `CAUSE_PAIRS` |
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
Slot 0 of each factor type → written into Main Row. Slots 1+ → new Detail Rows containing only the 8 key columns + that factor pair (all qty/production columns blank). `_expand_source_row()` handles this; `QPRBuilder.build()` falls back to the legacy `_resolve_row()` path when `cause_mapping` is absent or empty.

**`__copy_actual__` sentinel**: When `계획수량` rule is `DEFAULT/__copy_actual__`, `project_store.save_config()` resolves it to the source column name of `실적수량`.

**`_QPR_TO_CONFIG_KEY` in `project_store.py`**: The authoritative mapping from QPR column names → config.json keys. `None` values collect into `process_hierarchy[]` in order (대분류→[0], 중분류→[1], 소분류→[2]).

**MappingView UI architecture** (`ui/mapping_view.py`):  
Replaced QGraphicsScene/QGraphicsProxyWidget with plain widgets inside two `QScrollArea` panels:
- Left `QScrollArea` → `SourceColumnWidget` items
- `LineArea` (custom `paintEvent`) → draws connector lines using `mapToGlobal`/`mapFromGlobal` so scroll position is always accounted for
- Right `QScrollArea` → `QPRColumnWidget` items + `CauseGroupPanel` for each of the 3 factor types

`CauseGroupPanel` slots are added/removed dynamically. Factor qty columns (`비가동시간`, `부적합수량`, `불량수량`) are not shown as standalone rows; they live inside the panel's slot combos.

### Bridge Subsystem (`Bridge/`)

Standalone CLI for normalizing Lumicom "재공조회" WIP Excel files. Not integrated into the core parser/DB flow yet.

Pipeline: `file_finder` → `sheet_reader` (expand merged cells) → `header_mapper` (detect anchor row by "업체"+"DEVICE" keywords) → `row_processor` (forward-fill vendor, parse ints, compute `row_hash`) → `validator` → `output_writer`

Input filename pattern: `재공조회_YYMMDD.xlsx`. Sheet name pattern: `M.DD`.

### Project Workspaces (`projects/`)

Each project directory holds:
- `config.json` — parser-consumable (may be hand-authored for Project_A or auto-generated by Assist)
- `mapping_rules.json` — Assist-managed only (absent in Project_A)
- `output/` — QPR CSV outputs from Assist
- `raw/` — source data

`projects/Project_A/config.json` is the **reference structure** for all auto-generated `config.json` files.

# FOM_RULES

본 문서는 OpenFOMs의 기술 최상위 명세서다. FOM File Set 구조, 데이터 처리 흐름, 요인 모델, 프로젝트 공간 구조, 문서 체계, 코딩 원칙, MCP Server 명세, 데이터 보안 원칙을 정의한다. FOM 철학과 개념은 `README.md`를 참조한다.

---

## 1. FOM File Set

FOM File Set은 하나의 프로젝트 분석 단위를 구성하는 표준 데이터 파일 묶음이다. FOM 분석은 단일 QPR 파일만으로 완성되는 것이 아니라, 생산 실적·비가동·불량·부적합·기준값·비용 정보를 포함하는 **6개 파일 구조**를 기반으로 수행된다.

### 1.1 파일 구성

| 파일 | 역할 |
|------|------|
| `manual qpr_{YYYY}.csv` | 생산일자, Shift, 공정 계층, 설비, 제품, 작업자, 계획수량, 실적수량, 작업시간 등 생산 실적과 기본 4M 정보를 포함하는 **핵심 생산관리 파일** |
| `manual downtime.csv` | 비가동 유형 및 비가동 원인 정보를 정의하는 파일 |
| `manual reject.csv` | 불량 유형 및 불량 원인 정보를 정의하는 파일 |
| `manual abnormal.csv` | 부적합 유형 및 부적합 원인 정보를 정의하는 파일 |
| `manual limit.csv` | 달성률, 비가동률, 불량률, 부적합률 등 관리 기준값과 목표 수준을 정의하는 파일 |
| `manual cost.csv` | 제품별 단가 또는 비용 정보를 정의하여 손실비용 및 경제성 분석에 활용하는 파일 |

QPR 파일은 연도별로 분리하여 관리한다. `{YYYY}`는 해당 데이터의 연도를 나타내며, 예를 들어 2026년 데이터는 `manual qpr_2026.csv`로 저장된다. 하나의 프로젝트 폴더 안에 연도별 QPR 파일이 복수로 존재할 수 있다.

> **용어 참고 (부적합 영문 표기)**: 문서 내 설명·서술 목적으로는 "Nonconformity"와 "Abnormal"을 혼용해도 무방하다. 단, **FOM File Set 구성 요소(파일명, 코드 체계 등 실제 식별자)는 항상 `abnormal`을 사용**한다 (예: `manual abnormal.csv`). "nonconformity"를 파일명이나 식별자로 사용하지 않는다.

### 1.2 QPR 파일의 위치

`manual qpr_{YYYY}.csv`는 생산 실적과 4M 정보를 연결하는 중심 파일이며, 비가동·불량·부적합 발생 정보가 함께 기록될 수 있다. QPR은 FOM File Set 전체 중 하나의 구성요소이며, 요인 유형 정의·관리 기준·비용 정보는 나머지 5개 파일을 통해 보완된다.

**QPR(Quick Plan Result)** 은 현장 운영의 계획 대비 실적을 빠르게 확인한다는 의미의 범용 명칭으로, 현장 유형에 따라 컬럼 구성이 달라지며 각 현장별 QPR 구조는 별도 명세서로 정의한다.

### 1.3 프로젝트 로드 방식

FOM 분석은 **프로젝트 폴더 단위**로 열린다. 프로젝트를 열면 해당 폴더 내의 FOM File Set 전체를 자동으로 인식하고 불러온다.

- 폴더 내 `manual qpr_{YYYY}.csv` 파일은 연도별로 복수 존재할 수 있으며, 분석 시 대상 연도를 선택하거나 복수 연도를 합산하여 사용한다.
- `manual downtime.csv`, `manual reject.csv`, `manual abnormal.csv`, `manual limit.csv`, `manual cost.csv`는 연도 구분 없이 폴더 내 공통 파일로 관리된다.
- 파일이 존재하지 않는 경우, 해당 파일의 분석 기능은 비활성 상태로 처리하며 오류로 중단하지 않는다.

### 1.3 Assist 매핑 설정 파일

FOM File Set 데이터 파일 외에, Assist GUI가 변환 작업에 사용하는 설정 파일이 프로젝트 폴더에 함께 관리된다.

| 파일 | 역할 |
|------|------|
| `config.json` | 파서가 원천 컬럼을 해석하기 위한 프로젝트별 매핑 설정 |
| `mapping_rules.json` | Assist GUI가 관리하는 컬럼 매핑 규칙 (v2 포맷) |

---

## 2. FOM 데이터 흐름

```
현장 원천 데이터 (CSV / Excel)
        │
        ▼
  [Bridge]  비정형 원천 정규화
        │
        ▼
  [Assist]  정규화 데이터 → QPR 변환 (컬럼 매핑 GUI)
        │
        ▼
  FOM File Set (6개 파일)
  ┌──────────────────────────┐
  │  manual qpr_{YYYY}.csv   │  ← 핵심 생산관리 파일 (연도별)
  │  manual downtime.csv     │
  │  manual reject.csv       │
  │  manual abnormal.csv     │
  │  manual limit.csv        │
  │  manual cost.csv         │
  └──────────────────────────┘
        │
        ▼
  DB (SQLite)  TB_PRODUCTION + 요인 테이블 + TB_WARNING
        │
        ▼
  [Process 서브시스템]
  KPI 계산 · 4M 분석 · 손실 구조 진단
        │
        ▼
  [FOM MCP Server]  ← 단일 서버
  Resources : FOM 규칙 문서 노출
  Tools     : Process 분석 결과 조회
  Prompts   : FOM 철학 중심 응답 템플릿
        │
        ▼
  LLM 클라이언트 (Claude Desktop 등)
  사용자 자연어 질의 → FOM 도메인 답변
```

---

## 3. 요인(Factor) 데이터 모델

QPR의 요인 정보는 3개 유형으로 구분된다.

| 유형 | QPR 컬럼 | 설명 |
|------|----------|------|
| 비가동 (Downtime) | `비가동`, `비가동시간` | 설비·공정 정지 원인과 시간 |
| 부적합 (Nonconformity) | `부적합`, `부적합수량` | 규격·절차 부적합 발생 건수 |
| 불량 (Defect) | `불량`, `불량수량` | 품질 불량 발생 원인과 수량 |

요인은 하나의 작업 단위에 여러 건이 존재할 수 있으며, Detail Row 확장 구조로 수용한다. 세부 규칙은 `QPR_RULES.md` 3절을 참조한다.

> 부적합의 영문 표기는 설명상 "Nonconformity"를 사용하지만, 파일명·식별자는 1.1절 기준대로 `abnormal`을 따른다 (`manual abnormal.csv`).

---

## 4. 프로젝트 공간 구조

각 현장 프로젝트는 독립된 폴더로 관리된다. FOM 분석은 프로젝트 폴더를 열면 해당 폴더 내의 FOM File Set을 자동으로 인식하여 불러온다.

```
projects/
└── {프로젝트명}/
    ├── raw/                    원천 데이터 (가공 전)
    ├── output/                 QPR 변환 결과
    │   ├── manual qpr_2025.csv ← 연도별 QPR 파일
    │   ├── manual qpr_2026.csv
    │   ├── manual downtime.csv
    │   ├── manual reject.csv
    │   ├── manual abnormal.csv
    │   ├── manual limit.csv
    │   └── manual cost.csv
    ├── db/                     SQLite DB
    ├── logs/                   처리 로그
    ├── config.json             FOM File Set 설정
    └── mapping_rules.json      Assist 매핑 규칙
```

---

## 5. 문서 체계

| 문서 | 역할 | 대상 |
|------|------|------|
| `README.md` | FOM 철학·프로젝트 목적·4M + Objective Data 개념 | 전체 |
| `FOM_RULES.md` (본 문서) | 기술 최상위 명세 — File Set, 데이터 흐름, 문서 체계, MCP, 보안 | 개발자 |
| `QPR_RULES.md` | `manual qpr_{YYYY}.csv` 구조·Key·행 해석·파싱 변환 규칙 | 파서·개발자 |
| `COST_RULES.md` | `manual cost.csv` 구조·Key·QPR 연결 규칙 | 파서·개발자 |
| `DOWNTIME_RULES.md` | `manual downtime.csv` 구조·요인명 Key·QPR 연결 규칙 | 파서·개발자 |
| `REJECT_RULES.md` | `manual reject.csv` 구조·요인명 Key·QPR 연결 규칙 | 파서·개발자 |
| `ABNORMAL_RULES.md` | `manual abnormal.csv` 구조·요인명 Key·QPR 연결 규칙 | 파서·개발자 |
| `LIMIT_RULES.md` | `manual limit.csv` 구조·복합키·QPR 연결 및 판정 규칙 | 파서·개발자 |
| `ASSIST_RULES.md` | Assist GUI 입력 규칙·매핑 방식·출력 기준 | Assist·개발자 |
| `CLAUDE.md` | 코드 아키텍처·실행 명령·AI 코딩 지침 | AI·개발자 |

---

## 6. FOM Architecture Constraints

The following constraints must be respected in all design and implementation decisions. These guard against common misinterpretations of FOM.

- **FOM is the core philosophy.** AI, MCP, and external interfaces are secondary. They serve FOM analysis — FOM does not serve them.
- **QPR is a standardized file structure, not an analysis engine.** QPR defines how field data is recorded. Analysis logic belongs in the Process subsystem.
- **FOM File Set consists of multiple files, not only QPR.** `manual qpr_{YYYY}.csv` is the central file, but `manual downtime.csv`, `manual reject.csv`, `manual abnormal.csv`, `manual limit.csv`, and `manual cost.csv` are all required parts of the set.
- **Objective Data is an extensible dimension (e.g., Energy), not Plan/Result.** It is an independent measurement axis added alongside 4M — not a comparison between planned and actual values.
- **Do not redesign FOM into an AI-centric system.** LLM and MCP are interfaces for accessing FOM analysis results. The 4M-based analytical structure must remain the foundation.

---

## 7. Vibe Coding 원칙

FOM-AI 환경에서 코드를 생성하거나 수정할 때 따르는 원칙이다.

- **규칙 우선**: 구현 전에 `FOM_RULES.md` → `QPR_RULES.md` → `COST_RULES.md` → `ASSIST_RULES.md` 순으로 관련 규칙을 먼저 확인한다.
- **프로젝트 가변성 존중**: `process_hierarchy`의 도메인 의미는 프로젝트마다 다르다. 코드에서 대/중/소분류를 고정 의미로 가정하지 않는다.
- **요인 다중성 처리**: 비가동·부적합·불량은 복수 건이 발생할 수 있다. 단일값 가정으로 설계하지 않는다.
- **JSON 포맷 버전 관리**: `mapping_rules.json`은 v2 포맷을 기본으로 하며, v1 자동 마이그레이션 로직을 유지한다.
- **경고와 오류 분리**: 변환 불가 오류와 품질 경고를 별도 채널로 처리하며, 경고는 변환을 막지 않는다.

---

## 8. FOM MCP Server

### 8.1 설계 원칙

- **단일 서버**: 모든 프로젝트를 하나의 MCP 서버 인스턴스로 서비스한다. 프로젝트 구분은 Tool 파라미터(`project`)로 처리한다.
- **LLM 독립**: 특정 LLM 클라이언트에 종속되지 않는 표준 MCP 구조로 구현한다. 초기에는 Claude Desktop을 우선 대상으로 한다.
- **얇은 인터페이스**: 비즈니스 로직(KPI 계산, 분석)은 Process 서브시스템이 담당한다. MCP 서버는 Process 함수를 호출하고 결과를 LLM에 전달하는 역할만 한다.

### 8.2 제공 항목

#### Resources (FOM 도메인 지식)

| URI | 내용 |
|-----|------|
| `fom://rules/philosophy` | README.md 전문 |
| `fom://rules/fom` | FOM_RULES.md 전문 |
| `fom://rules/qpr` | QPR_RULES.md 전문 |
| `fom://project/{name}/config` | 프로젝트별 config.json |

#### Tools (Process 서브시스템 연동)

| Tool | 설명 |
|------|------|
| `get_production_summary` | 기간·프로젝트별 생산 실적 요약 (달성률 포함) |
| `get_downtime_analysis` | 비가동 요인별 시간 집계 (설비·공정 단위) |
| `get_defect_analysis` | 불량·부적합 요인별 수량 집계 (제품·작업자 단위) |
| `get_kpi_dashboard` | 4M 관점 KPI 종합 조회 |
| `get_warnings` | DB 적재 시 발생한 데이터 품질 경고 목록 |
| `list_projects` | 등록된 프로젝트 목록 및 최신 데이터 일자 |

#### Prompts (FOM 철학 중심 응답 템플릿)

| Prompt | 설명 |
|--------|------|
| `analyze_loss_structure` | 4M 관점의 손실 구조 분석 템플릿 |
| `daily_production_review` | 일일 생산 현황 FOM 진단 템플릿 |

### 8.3 구현 스택

- **언어**: Python (현 프로젝트와 동일)
- **MCP SDK**: `mcp` 패키지 (`pip install mcp`)
- **진입점**: `mcp_server/main.py`
- **환경변수**: `FOM_ROOT` — OpenFOMs 루트 경로

### 8.4 Process 서브시스템과의 인터페이스

MCP Tools는 Process 서브시스템의 함수를 직접 import하여 호출한다. HTTP나 별도 프로세스 통신 없이 동일 Python 환경에서 실행한다.

```
mcp_server/
├── main.py          MCP 서버 진입점 (Resources · Tools · Prompts 등록)
├── resources.py     FOM 규칙 문서 로더
├── tools.py         Process 서브시스템 호출 래퍼
└── prompts.py       FOM 철학 중심 프롬프트 템플릿
```

---

## 9. 데이터 보안 원칙

OpenFOMs는 "데이터는 고객 로컬에, AI 두뇌만 외부에서 빌린다"는 원칙으로 현장 데이터 유출 우려를 구조적으로 해소한다.

### 9.1 데이터 경계 정의

| 구분 | 위치 | 외부 전송 여부 |
|------|------|--------------|
| 원시 생산 데이터 (FOM File Set) | 고객 로컬 | **전송 안 함** |
| SQLite DB | 고객 로컬 | **전송 안 함** |
| 매핑 규칙 / config.json | 고객 로컬 | **전송 안 함** |
| FOM 규칙 문서 | 고객 로컬 | MCP Resource로 LLM에 전달 (기밀 아님) |
| 사용자 자연어 질문 | — | LLM API 전송 |
| MCP Tool 결과 (집계된 KPI) | — | LLM API 전송 (가공된 수치만) |

### 8.2 외부 전송 최소화 원칙

MCP Tool은 원시 데이터를 반환하지 않는다. Process 서브시스템에서 집계·계산된 결과만 반환하여 LLM API로 전달되는 데이터 양과 민감도를 최소화한다.

```
# 허용 — 집계된 KPI 수치
불량률: 2.3% / 비가동 합계: 45분 / 달성률: 94.8%

# 금지 — 원시 행 데이터 반환
[{"일자": "2025-01-03", "작업자": "홍길동", "제품": "D280", ...}, ...]
```

### 9.3 식별자 마스킹 (선택 옵션)

프로젝트 설정에서 식별자 마스킹을 활성화하면 Tool 결과의 고유 식별자가 익명화된다. 원본↔마스킹 매핑 테이블은 로컬 DB에만 저장된다.

```json
{ "security": { "mask_identifiers": true } }
```

### 9.4 LLM 백엔드 선택

MCP 서버는 LLM 백엔드에 독립적으로 설계된다. Tool 인터페이스는 동일하게 유지되며 백엔드만 교체할 수 있다.

| 백엔드 | 외부 전송 | 성능 | 비용 |
|--------|----------|------|------|
| Claude API | 집계 결과만 | 최고 | 종량제 |
| ChatGPT API | 집계 결과만 | 최고 | 종량제 |
| Ollama (로컬 모델) | 없음 | 중간 | 인프라 비용 |

### 9.5 API 데이터 처리 정책

Claude API(Anthropic) 및 ChatGPT API(OpenAI) 모두 API 입력·출력 데이터를 모델 학습에 사용하지 않는다고 명시하고 있다. 보다 강한 계약 보장이 필요한 경우 각 제공사의 기업용 Zero Data Retention 옵션을 활용한다.

> 고객사 제안 시 본 섹션을 근거 자료로 활용한다.

---

## 10. FOM KPI 코드 체계

### 10.1 유기적 연결 원칙

FOM Solution의 핵심 특징은 **관리번호(FOM Code)에 따라 모든 분석 컴포넌트가 유기적으로 연결**된다는 데 있다. FOM Code는 단순한 분류 번호가 아니라, 생산량·비가동·불량·부적합 영역의 분석 컴포넌트를 동일한 체계로 연결하는 키(key)다. 이를 통해 낭비요인 및 생산성 저해요인에 대한 분석·변화관리·추적관리가 가능해진다.

### 10.2 FOM Code 구조

FOM Code는 `#1000 ~ #4500` 범위에서 4개 영역으로 관리된다. 각 영역은 4M 관점(Total / Product / Machine / Worker / Factor)으로 세분화된다.

| 영역 | 코드 | Total | Product | Machine | Worker | Factor |
|------|------|-------|---------|---------|--------|--------|
| 생산량 (Product volume) | 1000 | 1100 | 1200 | 1300 | 1400 | — |
| 비가동 (Downtime) | 2000 | 2100 | 2200 | 2300 | 2400 | 2500 |
| 불량 (Defect) | 3000 | 3100 | 3200 | 3300 | 3400 | 3500 |
| 부적합 (Nonconformity) | 4000 | 4100 | 4200 | 4300 | 4400 | 4500 |

> 위 표의 "Nonconformity"는 설명용 영문 표기이며, 파일명·식별자 기준은 `abnormal`이다 (1.1절 참조).

### 10.3 분석 단위

FOM 분석은 시간 단위와 공간 단위를 조합하여 수행한다.

**시간 단위**

| 단위 | 설명 |
|------|------|
| Yearly | 연간 집계 |
| Monthly | 월간 집계 |
| Weekly | 주간 집계 |
| Daily | 일간 집계 |
| Shift | 주·야 또는 8시간 단위 |

**공간 단위 (3단계)**

| 단계 | 명칭 | 설명 |
|------|------|------|
| 1단계 | Factory | 공장 전체 |
| 2단계 | Production line | 생산 라인 (공정 계층 Level1~2) |
| 3단계 | Production detail line | 생산 세부 라인 (공정 계층 Level3) |

### 10.4 FOM Code 활용 방법

| 방법 | 설명 |
|------|------|
| **FOM Code별 분석** | 특정 코드(예: #2300 Machine Downtime)를 기준으로 해당 영역의 손실 현황을 단독 분석 |
| **변화관리** | 동일 코드 기준으로 기간별 추이를 추적하여 개선 전후 변화를 정량적으로 관리 |
| **비교분석** | 동일 코드를 기준으로 설비 간, 작업자 간, 제품 간, 기간 간 비교 분석 수행 |

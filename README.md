<div align="center">
<img src="http://www.df.re.kr/img/main/main_flash22.gif" />
</div>

# OpenFOMs
본 프로젝트는 제조현장에서 생성되는 생산 데이터를 기반으로 Factory Operation Management(FOM) 시스템 중심의 데이터 기반 분석 프레임워크를 구축하는 것을 목적으로 한다. 이를 위해 현장 데이터를 표준화된 FOM 파일셋으로 재구성하고, 데이터 정합성을 확보하며, 4M(Man, Machine, Material, Method)과 Objective Data를 결합한 확장 가능한 분석 구조를 설계한다. 또한 KPI 중심의 다차원 분석을 통해 공정, 설비, 작업자 단위의 성과를 정량적으로 진단하고 운영 손실 및 개선 기회를 도출한다. 더불어 FOM 철학을 기반으로 Vibe Coding과 FOM-AI의 핵심 요소를 구현하여, 데이터 전처리(Assist)와 분석(Process)이 통합된 지능형 분석 환경을 구축한다.

This project focuses on developing a data-driven analysis framework based on the Factory Operation Management (FOM) system by integrating production data and energy data from manufacturing environments. The study aims to restructure raw shop-floor data into a standardized FOM file set, ensure data integrity, and establish KPI-based analytical models aligned with 4M1E (Man, Machine, Material, Method, Energy).

In particular, energy consumption data collected from FEMS is redefined and linked with production performance to move beyond traditional energy-saving approaches toward productivity-oriented operational strategies. The system supports multidimensional analysis, enabling identification of operational losses and improvement opportunities through KPI codes such as #5100–#5500.

The ultimate goal is to provide a scalable FOM-based analysis environment that allows flexible data preprocessing (Assist) and structured analytical processes (Process), supporting decision-making and continuous improvement in smart manufacturing systems.

---

```
프로젝트 = 데이터 공간 + 실행 컨텍스트
```
단순히 폴더만 나누면 부족하고, **폴더 + DB + 메타정보 + 세션 컨텍스트**까지 함께 설계해야 안정적으로 동작한다.

---

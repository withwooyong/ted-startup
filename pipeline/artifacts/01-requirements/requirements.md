---
agent: "01-biz-analyst"
stage: "01-requirements"
version: "1.0.0"
created_at: "2026-04-16T15:00:00+09:00"
depends_on:
  - "pipeline/artifacts/00-input/user-request.md"
quality_gate_passed: false
changelog:
  - version: "1.0.0"
    changes: "Initial creation"
---

# 요구사항 분석서 — 공매도 커버링 시그널 탐지 시스템

## 프로젝트명
shortsell-covering-signal (공매도 커버링 시그널 탐지기)

## 비즈니스 목표

```yaml
business_goals:
  - goal: "대차잔고 급감 종목을 자동 탐지하여 숏커버링 랠리 진입 시점 포착"
    success_metric: "시그널 발생 후 5거래일 내 양의 수익률 달성 비율 60% 이상"
  - goal: "KRX 공개 데이터만으로 법적 리스크 없는 개인 투자 참고 도구 구축"
    success_metric: "사용 데이터 100% KRX 공개 데이터, 면책 고지 표시율 100%"
  - goal: "일 1회 배치 자동화로 수동 데이터 분석 시간 제거"
    success_metric: "일일 분석 소요시간 2시간 → 0분 (자동화)"
  - goal: "백테스팅으로 시그널 신뢰도를 객관적으로 검증"
    success_metric: "과거 3년 데이터 기반 시그널별 적중률/수익률 리포트 생성"
```

## 사용자 스토리

```yaml
user_stories:
  - id: US-001
    as_a: "개인 투자자"
    i_want: "매일 아침 대차잔고가 급감한 종목 리스트를 받고 싶다"
    so_that: "숏커버링 랠리 가능성이 높은 종목을 빠르게 파악할 수 있다"
    acceptance_criteria:
      - "전일 대비 대차잔고 감소율 상위 종목이 정렬되어 표시된다"
      - "감소율, 감소량, 연속 감소일수가 함께 표시된다"
      - "텔레그램으로 요약 알림을 받을 수 있다"
    priority: "Must"

  - id: US-002
    as_a: "개인 투자자"
    i_want: "대차잔고 추세가 전환(하락→상승 또는 상승→하락)되는 종목을 감지하고 싶다"
    so_that: "공매도 세력의 포지션 변화를 조기에 인지할 수 있다"
    acceptance_criteria:
      - "5일/20일 이동평균 교차(골든/데드크로스) 시점이 표시된다"
      - "추세 전환 강도(약/중/강)가 스코어로 표시된다"
    priority: "Must"

  - id: US-003
    as_a: "개인 투자자"
    i_want: "숏스퀴즈 가능성을 종합 스코어로 확인하고 싶다"
    so_that: "여러 지표를 일일이 분석하지 않고 한눈에 판단할 수 있다"
    acceptance_criteria:
      - "대차잔고 감소율, 거래량 급증, 가격 상승, 공매도 비율 등을 종합한 스코어(0~100)"
      - "스코어 기준별 등급(A/B/C/D) 분류"
      - "스코어 산출 근거가 tooltip으로 표시된다"
    priority: "Must"

  - id: US-004
    as_a: "개인 투자자"
    i_want: "종목별 대차잔고 추이를 차트로 보고 싶다"
    so_that: "시계열 패턴을 시각적으로 확인할 수 있다"
    acceptance_criteria:
      - "일별 대차잔고 추이 라인 차트"
      - "주가와 대차잔고를 듀얼 축으로 비교 가능"
      - "시그널 발생 시점이 차트에 마커로 표시된다"
      - "조회 기간 선택 가능 (1개월/3개월/6개월/1년)"
    priority: "Must"

  - id: US-005
    as_a: "개인 투자자"
    i_want: "과거 시그널의 적중률을 백테스팅으로 검증하고 싶다"
    so_that: "시그널의 신뢰도를 객관적으로 판단할 수 있다"
    acceptance_criteria:
      - "과거 3년간 시그널 발생 건수, 적중률, 평균 수익률 표시"
      - "시그널 타입별(급감/추세전환/숏스퀴즈) 분리 통계"
      - "보유 기간(5일/10일/20일)별 수익률 비교"
    priority: "Must"

  - id: US-006
    as_a: "개인 투자자"
    i_want: "텔레그램으로 매일 시그널 요약을 받고 싶다"
    so_that: "대시보드에 접속하지 않아도 핵심 정보를 확인할 수 있다"
    acceptance_criteria:
      - "매일 오전 8시 30분에 시그널 요약 메시지 발송"
      - "상위 5개 종목의 종목명, 시그널 타입, 스코어 포함"
      - "면책 고지 문구 포함"
    priority: "Must"

  - id: US-007
    as_a: "개인 투자자"
    i_want: "시장 전체의 공매도 동향을 한눈에 보고 싶다"
    so_that: "개별 종목 분석 전에 시장 분위기를 파악할 수 있다"
    acceptance_criteria:
      - "KOSPI/KOSDAQ 전체 공매도 거래대금 추이"
      - "대차잔고 총액 추이"
      - "공매도 과열 업종 TOP 5"
    priority: "Should"

  - id: US-008
    as_a: "개인 투자자"
    i_want: "시그널 임계값을 커스터마이징하고 싶다"
    so_that: "내 투자 성향에 맞게 민감도를 조정할 수 있다"
    acceptance_criteria:
      - "대차잔고 감소율 임계값 조정 (기본 -10%)"
      - "숏스퀴즈 스코어 알림 기준 조정 (기본 70점)"
      - "설정 저장 및 불러오기"
    priority: "Should"

  - id: US-009
    as_a: "개인 투자자"
    i_want: "관심 종목(워치리스트)을 등록하고 해당 종목의 시그널만 집중 모니터링하고 싶다"
    so_that: "관심 종목의 공매도 변동을 놓치지 않을 수 있다"
    acceptance_criteria:
      - "종목 검색 및 워치리스트 추가/삭제"
      - "워치리스트 종목 시그널 우선 표시"
      - "워치리스트 종목 변동 시 별도 알림"
    priority: "Should"

  - id: US-010
    as_a: "개인 투자자"
    i_want: "업종별 공매도 분석을 보고 싶다"
    so_that: "특정 업종에 공매도가 집중되는 패턴을 파악할 수 있다"
    acceptance_criteria:
      - "업종별 공매도 비율 히트맵"
      - "업종별 대차잔고 변동 추이"
    priority: "Could"

  - id: US-011
    as_a: "개인 투자자"
    i_want: "시그널 발생 이력을 조회하고 싶다"
    so_that: "과거 어떤 시그널이 발생했고 이후 주가가 어떻게 변했는지 학습할 수 있다"
    acceptance_criteria:
      - "날짜/종목/시그널타입으로 필터링"
      - "시그널 발생 후 5/10/20일 수익률 표시"
    priority: "Should"

  - id: US-012
    as_a: "개인 투자자"
    i_want: "모든 시그널 화면에 면책 고지가 표시되어야 한다"
    so_that: "투자 자문이 아닌 정보 제공 도구임을 명확히 인지할 수 있다"
    acceptance_criteria:
      - "모든 페이지 하단에 면책 고지 고정 표시"
      - "시그널 상세 화면에 '투자 판단의 책임은 본인에게 있습니다' 문구"
      - "텔레그램 알림에도 면책 고지 포함"
    priority: "Must"
```

## 기능 요구사항

```yaml
functional_requirements:
  - id: FR-001
    description: "KRX 공매도 통계 데이터 일 1회 배치 수집 (공매도 거래대금, 대차잔고)"
    related_user_stories: [US-001, US-002, US-003]
  - id: FR-002
    description: "KRX 시세 데이터 일 1회 배치 수집 (종가, 거래량, 시가총액)"
    related_user_stories: [US-001, US-004]
  - id: FR-003
    description: "대차잔고 급감 시그널 탐지 (전일 대비 감소율 기반)"
    related_user_stories: [US-001]
  - id: FR-004
    description: "대차잔고 추세전환 시그널 탐지 (이동평균 교차 기반)"
    related_user_stories: [US-002]
  - id: FR-005
    description: "숏스퀴즈 종합 스코어링 (다중 지표 가중 합산)"
    related_user_stories: [US-003]
  - id: FR-006
    description: "종목별 대차잔고/주가 듀얼 축 차트 렌더링"
    related_user_stories: [US-004]
  - id: FR-007
    description: "과거 3년 데이터 기반 백테스팅 엔진"
    related_user_stories: [US-005]
  - id: FR-008
    description: "텔레그램 Bot API 연동 시그널 알림"
    related_user_stories: [US-006]
  - id: FR-009
    description: "시장 전체 공매도 동향 대시보드"
    related_user_stories: [US-007]
  - id: FR-010
    description: "시그널 임계값 사용자 설정"
    related_user_stories: [US-008]
  - id: FR-011
    description: "워치리스트 관리 (CRUD + 시그널 우선 표시)"
    related_user_stories: [US-009]
  - id: FR-012
    description: "면책 고지 전역 표시 (웹 + 텔레그램)"
    related_user_stories: [US-012]
```

## 비기능 요구사항

```yaml
non_functional_requirements:
  - id: NFR-001
    category: "Performance"
    target_metric: "배치 수집 완료 시간 < 10분 (전 종목 기준)"
  - id: NFR-002
    category: "Performance"
    target_metric: "대시보드 초기 로딩 < 3초, 차트 렌더링 < 1초"
  - id: NFR-003
    category: "Performance"
    target_metric: "백테스팅 3년 데이터 처리 < 5분"
  - id: NFR-004
    category: "Scalability"
    target_metric: "KOSPI + KOSDAQ 전 종목(~2,500개) 처리 가능"
  - id: NFR-005
    category: "Reliability"
    target_metric: "배치 실패 시 자동 재시도 (최대 3회), 실패 알림"
  - id: NFR-006
    category: "Security"
    target_metric: "텔레그램 Bot Token 환경변수 관리, DB 접속 정보 암호화"
  - id: NFR-007
    category: "Data Retention"
    target_metric: "시계열 데이터 3년 보관, 월별 파티셔닝"
  - id: NFR-008
    category: "Availability"
    target_metric: "개인용이므로 SLA 불필요, 다만 배치 정시 실행률 95% 이상"
```

## 리스크

```yaml
risks:
  - id: RISK-001
    description: "KRX 데이터 포맷/API 변경 시 수집 실패"
    impact: "High"
    mitigation: "데이터 수집 레이어 추상화, 포맷 변경 감지 알림, 수동 보정 도구"
  - id: RISK-002
    description: "대차잔고 데이터가 실제 공매도 포지션을 정확히 반영하지 않을 수 있음 (장외 거래 등)"
    impact: "Medium"
    mitigation: "면책 고지 명시, 시그널을 '참고용'으로만 제공, 백테스팅으로 한계 투명하게 공개"
  - id: RISK-003
    description: "KRX 웹사이트 크롤링 시 IP 차단 가능성"
    impact: "Medium"
    mitigation: "요청 간격 2초 이상, User-Agent 정상 설정, 공식 Open API 전환 대비"
  - id: RISK-004
    description: "시그널 과적합 — 백테스트에서는 좋으나 실전 성과 괴리"
    impact: "High"
    mitigation: "학습기간/검증기간 분리 (Walk-forward), 파라미터 과최적화 방지"
  - id: RISK-005
    description: "투자 자문으로 오해받을 법적 리스크"
    impact: "High"
    mitigation: "모든 화면/알림에 면책 고지, 개인 내부 도구로만 사용, 외부 배포 금지"
```

## 경쟁 서비스 벤치마킹

| 서비스 | 특징 | 강점 | 약점 |
|--------|------|------|------|
| **공매도 닷컴** (shortselling.kr) | 공매도 잔고/거래 현황 제공, 종목별 공매도 추이 차트 | 무료, 직관적 UI, 실시간 업데이트 | 시그널 탐지 없음, 알림 없음, 분석 도구 부재 |
| **DeepSearch** (deep-search.io) | AI 기반 투자 분석, 공매도 데이터 포함 | AI 인사이트, 뉴스 연계 분석 | 유료($50+/월), 공매도 특화 아님, 개인 커스터마이징 불가 |
| **퀀트킹** (quantking.co.kr) | 퀀트 투자 백테스팅, 팩터 분석 | 백테스팅 기능, 다양한 팩터 | 공매도 특화 아님, 대차잔고 시그널 없음 |

**차별화 포인트**: 대차잔고/공매도 특화 + 자동 시그널 탐지 + 백테스팅 + 텔레그램 알림을 하나로 통합한 개인용 도구.

## MVP 범위 (4~6주)

```yaml
mvp_scope:
  included:
    - "FR-001: KRX 데이터 배치 수집 (공매도 + 시세)"
    - "FR-002: KRX 시세 데이터 수집"
    - "FR-003: 대차잔고 급감 시그널"
    - "FR-004: 추세전환 시그널"
    - "FR-005: 숏스퀴즈 종합 스코어"
    - "FR-006: 종목별 차트 (대차잔고 + 주가)"
    - "FR-007: 백테스팅 (3년)"
    - "FR-008: 텔레그램 알림"
    - "FR-012: 면책 고지"
  deferred:
    - "FR-009: 시장 전체 동향 대시보드 → v1.1"
    - "FR-010: 시그널 임계값 커스터마이징 → v1.1"
    - "FR-011: 워치리스트 → v1.2"
    - "업종별 분석 (US-010) → v2"
    - "시그널 이력 조회 (US-011) → v1.1"
```

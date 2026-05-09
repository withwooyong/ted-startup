# CLAUDE.md — backend_kiwoom

> 이 파일은 `src/backend_kiwoom/` 하위 작업 시 Claude Code 에게 적용되는 규칙. 프로젝트 루트 `CLAUDE.md` 와 사용자 글로벌 `~/.claude/CLAUDE.md` 의 규칙은 그대로 상속.

---

## 1. STATUS.md 자동 갱신 규칙 (필수)

`src/backend_kiwoom/STATUS.md` 는 **단일 진실 출처** — 전체 작업의 진척을 한 화면에서 파악하기 위한 문서.

### 1.1 트리거 — 언제 갱신하는가

다음 중 **하나라도** 발생하면 같은 응답 안에서 STATUS.md 도 함께 수정한다:

- chunk 단위 작업 완료 (커밋 직전 또는 커밋 동일 turn)
- 새로운 endpoint 코드/테스트가 머지 가능한 상태로 마무리됨
- 새로운 운영 검증 / dry-run 결과가 ADR 에 기록됨
- 새로운 알려진 이슈 / 위험이 발견되어 별도 chunk 로 이월 결정됨
- 다음 chunk 우선순위 / 옵션이 변경됨

### 1.2 갱신 대상 섹션 (STATUS.md § 7 체크리스트)

매 chunk 커밋 직후, 아래 섹션 중 **변경이 발생한 곳만** 수정. 변경 없으면 건드리지 않음.

- [ ] **§ 0 한눈에 보기** — 마지막 완료 chunk / 다음 chunk / 25 endpoint 진행률 / 테스트 cases 수 + coverage / 누적 chunk 수
- [ ] **§ 1 Phase 진척** — 해당 Phase 의 chunk 진행 컬럼 + 상태(✅/🔄/⏳) 갱신
- [ ] **§ 2 25 Endpoint 카탈로그** — endpoint 이동 (대기 → 다음 → 완료). 완료 row 에 chunk 명/커밋 해시 추가
- [ ] **§ 3 Phase C 세부** (Phase C 진행 중에만) — sub-chunk 상태(✅/🔄/⏳) + 산출물 컬럼 갱신
- [ ] **§ 4 알려진 이슈** — 해소된 항목 제거 / 신규 발견 항목 추가 (ADR / dry-run 출처 명시)
- [ ] **§ 5 다음 chunk 후보** — 우선순위 재조정. 방금 완료한 chunk 는 § 6 으로 이동
- [ ] **§ 6 Phase A~B 완료 목록** — Phase A/B/(C 완료 후) 새 chunk 추가 (chunk 명, 한 줄 요약, 커밋 해시)
- [ ] **마지막 갱신 날짜** (문서 상단) — 오늘 날짜로 변경 (KST 기준)

### 1.3 갱신 흐름

`HANDOFF.md` 갱신 → `CHANGELOG.md` 갱신 → **`STATUS.md` 갱신** → 커밋. 세 문서 동시 갱신을 권장.

> `HANDOFF.md` = 직전 세션 단면 / `CHANGELOG.md` = 시간순 변경 로그 / `STATUS.md` = **진척 누적 + 향후 조망**. 역할이 다르므로 같은 chunk 라도 세 문서 모두 갱신 대상이 될 수 있음.

### 1.4 커밋 포함 여부

STATUS.md 변경은 **해당 chunk 커밋과 동일 commit 에 포함**. 별도 commit 으로 분리하지 않는다 (HANDOFF.md / CHANGELOG.md 와 동일 정책).

### 1.5 예외 — 갱신 생략 가능

다음 경우엔 STATUS.md 를 갱신하지 않아도 됨:

- 단순 typo / 주석 / 포맷팅 fix (chunk 구분 자체가 없는 micro-commit)
- 본 STATUS.md 자체의 메타 수정 (자기 갱신 무한 루프 차단)
- 코드 변경 없는 단순 문서 갱신 (단, 새로운 결정 / 이슈 / 우선순위 변경 시는 갱신 필요)

---

## 2. 기존 문서 역할 분담 (참고)

| 문서 | 역할 | 갱신 시점 |
|------|------|-----------|
| `STATUS.md` | **진척 단일 진실 출처** (전체 + 누적 + 다음) | chunk 완료 시 (§ 1 규칙) |
| `HANDOFF.md` | 직전 세션 단면 + 다음 옵션 | 세션 종료 시 |
| `CHANGELOG.md` | 시간순 chunk 단위 변경 로그 | chunk 커밋 직전 prepend |
| `docs/plans/master.md` | 전체 설계 / Phase 분할 / 25 endpoint 카탈로그 | 설계 변경 시만 |
| `docs/plans/endpoint-NN-*.md` | endpoint 별 상세 DoD + chunk 별 § | chunk 진행 시 (§ 추가 또는 DoD 체크) |
| `docs/ADR/ADR-0001-*.md` | 결정 누적 로그 | 결정 발생 시 새 § 추가 |

---

## 3. backend_kiwoom 작업 시 추가 권고

- 새로운 endpoint 코드화 chunk 진입 전, **plan doc 에 chunk 전용 § 추가** (영향 범위 / 위험 self-check / DoD) 가 이전 chunk 들의 정착된 패턴 (C-2γ 가 latest 예시). 이 패턴을 유지.
- `/ted-run` 풀 파이프라인은 plan doc 의 chunk § 를 input 으로 받아 동작. 따라서 STATUS.md § 5 다음 chunk 후보가 plan doc § 와 매핑되어야 함.
- 운영 dry-run / KOSCOM cross-check 같이 **코드 변경 0** 인 검증 chunk 도 STATUS.md § 6 + § 4 갱신 대상.

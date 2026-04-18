# KIS AI Extensions 통합 가능성 평가

**작성일**: 2026-04-18
**상태**: 조사 완료 — **통합 보류**. 레퍼런스 자료로만 활용.
**관련 플랜**: `docs/migration/java-to-python-plan.md` §11 P11 (KIS REST 모의 연동)
**조사 소스**:
- https://github.com/koreainvestment/kis-ai-extensions (공식, 142★, 최신 커밋 2026-04-17)
- https://apiportal.koreainvestment.com/apiservice-apiservice (KIS OpenAPI 포털)

## 1. 결론 요약

| 항목 | 판단 |
|---|---|
| KIS OpenAPI 자체 채택 | **채택** (P11 계획 그대로) — KRX 익명 차단 블로커 우회 수단 |
| kis-ai-extensions 플러그인 통합 | **보류** — 스코프 불일치 + 외부 의존 과다 |
| 레퍼런스 활용 | **권장** — 자체 에이전트/스킬 설계에 참고 |

## 2. kis-ai-extensions 구성

### 2.1 기본 정보
- 공식 레포 (korea-investment 조직)
- **라이선스 명시 없음** → 프로덕션 통합 시 법무 검토 필수
- npm 패키지: `@koreainvestment/kis-quant-plugin`
- 설치: `npx @koreainvestment/kis-quant-plugin init --agent claude`
- 전제 조건: `open-trading-api` 레포 clone, Python 3.11+, uv, Node 18+, **Docker**(Lean 엔진), KIS 앱키/시크릿

### 2.2 Claude Code 지원 범위
설치 시 `.claude/` 와 `.mcp.json` 자동 생성 — 1급 지원.

| 카테고리 | 항목 |
|---|---|
| Skills | `kis-strategy-builder`, `kis-backtester`, `kis-order-executor`, `kis-team`, `kis-cs` |
| Commands | `/auth [vps\|prod\|ws\|switch]`, `/kis-setup`, `/my-status`, `/kis-help` |
| Hooks | `kis-secret-guard`(appkey 유출 차단, PreToolUse), `kis-prod-guard`(실전 주문 확인, PreToolUse), `kis-trade-log`(PostToolUse), `kis-mcp-log`(PostToolUse) |
| MCP 서버 | `kis-backtest` @ `http://127.0.0.1:3846/mcp` (Docker 기반 QuantConnect Lean 엔진) |

### 2.3 MCP 제공 도구
- `run_backtest` — 프리셋 또는 `.kis.yaml` 전략으로 백테스트
- `optimize_params` — Grid/Random 파라미터 최적화
- `get_report` — HTML 리포트 조회
- `list_strategies` — 사용 가능한 전략 목록

### 2.4 내장 프리셋 (10종)
골든크로스, 모멘텀, 52주 신고가, 연속 상승/하락, 이격도, 돌파 실패, 강한 종가, 변동성 확장, 평균회귀, 추세 필터. 80개 기술지표 조합 가능.

## 3. KIS OpenAPI 본체

| 항목 | 내용 |
|---|---|
| 자산군 | 국내/해외 주식·선물옵션, 장내채권 |
| 기능 | 주문·계좌, 기본시세, 시세분석, 순위분석, 실시간(WebSocket) |
| 인증 | OAuth(appkey/appsecret → 접근토큰 6h), Hashkey, WS 접속키 |
| 환경 | 실전/모의 둘 다 지원 |
| 호출 제한 | 포털 문서에 명시 없음. 모의 계좌는 `EGW00201`(초당 거래건수 초과) 빈발 — 연속 호출 많으면 실전 계좌 권장 |

## 4. ted-startup 프로젝트 관점 적합성

| 항목 | 평가 | 비고 |
|---|---|---|
| KIS API로 KRX 익명 차단 블로커 우회 | ★★★ | P11 계획 그대로. `kis_client.py`를 `dart_client.py` 옆에 직접 구현 |
| kis-ai-extensions를 이 레포에 설치 | ★☆☆ | `open-trading-api` 기생 구조 + Docker 요구 → 오버스펙 |
| MCP `kis-backtest` 를 P10~P15 에 활용 | ★★☆ | 자체 `vectorbt` 스택과 중복. 전략 탐색용 보조로만 가치 |
| 스킬/훅 설계 레퍼런스 | ★★★ | `kis-secret-guard`, `kis-prod-guard` 패턴은 자체 에이전트에 이식 가치 높음 |

## 5. 보류 이유

1. **스코프 불일치** — 플러그인은 "AI 에이전트로 자연어 전략·백테스트·주문" 중심. ted-startup 의 P10~P15 는 **포트폴리오 동기화 + AI 분석 리포트** 로 지향점이 다름.
2. **외부 의존** — `open-trading-api` 레포 필수, Docker 런타임 필수. 현재 FastAPI + SQLAlchemy + asyncio 스택에 이질적.
3. **백테스트 엔진 중복** — 마스터 설계서 기준 `vectorbt` 채택 확정. Lean 엔진 추가 시 유지보수 비용 2배.
4. **라이선스 불명확** — 프로덕션 반영 전 법적 검토 필요.
5. **플러그인 자체 안정성 미검증** — 스타 142, 최신 커밋 활발하나 실사용 레퍼런스 제한적.

## 6. 채용 권고 (이식 대상)

자체 구현 시 아래 패턴은 차용 권장:

- **보안 훅**: PreToolUse 에서 `appkey|appsecret|token` 정규식 하드코딩 차단 → `.claude/hooks/` 에 `kis-secret-guard.sh` 이식
- **실전 가드**: 실전 주문 직전 종목/수량/금액 표시 후 사용자 확인 강제
- **인증 모드 분리**: `vps`(모의) / `prod`(실전) / `ws`(실시간) 명시적 커맨드 분리
- **강도 게이트**: 신호 강도 < 0.5 시 주문 스킵하는 룰

## 7. 후속 작업

- [ ] P11 착수 시 `src/backend_py/app/adapter/out/external/kis_client.py` 직접 구현 (kis-ai-extensions 사용 안 함)
- [ ] 자체 `.claude/hooks/kis-secret-guard.sh` 작성 (§6 보안 훅 이식)
- [ ] 본 리포트는 P11 작업자가 레퍼런스로 참조

## 8. 레퍼런스

- [kis-ai-extensions 레포](https://github.com/koreainvestment/kis-ai-extensions)
- [open-trading-api 본체 레포](https://github.com/koreainvestment/open-trading-api)
- [KIS Developers 포털](https://apiportal.koreainvestment.com/)
- 관련 프로젝트 문서: `docs/migration/java-to-python-plan.md` §11 P11, `docs/research/kiwoom-rest-feasibility.md`

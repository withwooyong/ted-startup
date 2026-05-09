# phase-c-refactor-r1 — 일관 개선 (errors → tuple / StockMasterNotFoundError / LOW 3건)

## 0. 메타

| 항목 | 값 |
|------|-----|
| 분류 | refactor (외부 API 동작 무변, 내부 타입·예외 정리) |
| 범위 | 3 도메인 횡단 (fundamental / OHLCV / daily_flow) |
| 선행 chunk | B-γ-2 (`56dbad9`) / C-1β (`993874c`) / C-2β (`e442416`) / C-2γ (`f8cece0`) 모두 완료 |
| 우선순위 | P1 — 테스트 안정성 + 신규 chunk 진입 전 베이스 정리 |
| 선택 시점 | 2026-05-09 (사용자 결정 — STATUS § 5 #1) |
| 분량 추정 | ~600~800줄 (코드 7 + 테스트 6 + 문서 4) |

## 1. 목적

ADR-0001 § 19.5 (C-2β Defer 5건) + 동일 패턴이 C-1β / B-γ-2 에 잠재. 3 도메인 (fundamental / OHLCV / daily_flow) 의 service · router · 테스트를 한 번에 일관 정리하여:

1. **mutable container 노출 제거** — `errors: list[...]` → `tuple[...]` (Result dataclass 가 frozen 일관)
2. **예외 타입 안전성** — `ValueError("stock master not found: ...")` 메시지 검색 → 전용 예외 `StockMasterNotFoundError(ValueError)`
3. **DTO 메타 깔끔화** — `only_market_codes max_length=4` (pattern={1,2}) dead 정정 / `fetched_at: datetime | None` (ORM NOT NULL) 비-Optional 정정
4. **Exception 격리 의도 명시** — `refresh_one` NXT 처리의 `except KiwoomError` → `except Exception` 의 trade-off 결정 + 주석

3 도메인 패턴 일관성 회복 → 다음 chunk (C-3 주봉/월봉 / Phase D 분봉) 진입 시 동일 패턴 복제 안정성.

## 2. 범위 외 (Out of Scope)

- C-1β/C-2β 의 다른 Defer (GET 라우터 admin guard, date.today() vs datetime.now(KST), find_range adjusted 필터 등) — 운영 시점 결정
- C-2α 상속 (NUMERIC magnitude 가드 / idx_daily_flow_exchange cardinality)
- 새로운 endpoint / 신규 도메인
- 외부 API 동작 변화 (응답 status code / body 키)

> **외부 동작 불변 보장**: 본 chunk 의 모든 변경은 (a) 내부 타입 정리 (b) 예외 클래스 변경이지만 router 가 동일한 status/body 로 매핑 (c) DTO max_length / Optional 정정으로 잘못된 입력만 422 (이전엔 통과 후 에러 — 더 안전). API contract 무변.

## 3. 영향 범위 (코드 7 + 테스트 6 + 문서 4)

### 3.1 신규 모듈 (1)

| 파일 | 내용 |
|------|------|
| `app/application/exceptions.py` (신규 또는 기존 위치) | `class StockMasterNotFoundError(ValueError):` — message + `stock_code: str` 속성. ValueError 상속으로 기존 `except ValueError` 캐치 그대로 동작 (호환성). 새 분기는 `except StockMasterNotFoundError` 로 명시 |

> 위치 검토: 기존 `app/application/` 에 `exceptions.py` 가 있는지, 또는 service 별 inline 정의 패턴이 있는지 확인 후 결정 (없으면 신규).

### 3.2 Service 레이어 (3)

| 파일 | 변경 |
|------|------|
| `app/application/service/stock_fundamental_service.py` | (1) `errors: list[...]` 2 위치 → `tuple[..., ...]` 또는 build-then-freeze (`tuple(local_list)`). (2) `raise ValueError("stock master not found: ...")` → `raise StockMasterNotFoundError(stock_code)` |
| `app/application/service/ohlcv_daily_service.py` | 동일 패턴 (errors 3 위치 + 예외 1) + `refresh_one` NXT path `except KiwoomError` → `except Exception` 격리 + 주석 (의도 명시) |
| `app/application/service/daily_flow_service.py` | 동일 패턴 (errors 3 위치 + 예외 1 + Exception 격리) |

**`errors` 정리 방식**:
- `OhlcvSyncResult.errors: tuple[OhlcvSyncOutcome, ...] = field(default_factory=tuple)` — frozen dataclass 일관 (이미 frozen=True)
- service 내부에서는 local `list` 로 build → `OhlcvSyncResult(errors=tuple(local_errors))` 로 frozen 변환
- 테스트는 `result.errors[0]` 인덱싱은 그대로 동작 (tuple 도 sequence)

### 3.3 Router 레이어 (3)

| 파일 | 변경 |
|------|------|
| `app/adapter/web/routers/fundamentals.py` | (1) `FundamentalSyncResultOut.errors: tuple[...]` (2) `only_market_codes` `max_length=4` → `2` (3) `FundamentalRowOut.fetched_at: datetime` (non-Optional, ORM NOT NULL) (4) `if "stock master not found" in msg:` → `except StockMasterNotFoundError` 분기 |
| `app/adapter/web/routers/ohlcv.py` | 동일 4건 |
| `app/adapter/web/routers/daily_flow.py` | 동일 4건 |

> Pydantic `tuple[...]` 응답: Pydantic v2 가 sequence 직렬화 시 JSON array 로 변환 — JSON 응답 변화 없음. OpenAPI 스키마는 `array` 그대로.

### 3.4 테스트 (6 갱신)

| 파일 | 변경 |
|------|------|
| `tests/test_stock_fundamental_service.py` | `pytest.raises(ValueError, match="stock master not found")` → `pytest.raises(StockMasterNotFoundError)` 또는 둘 다 검증 (호환성). `errors` 인덱싱 그대로 |
| `tests/test_ingest_daily_ohlcv_service.py` | 동일 |
| `tests/test_ingest_daily_flow_service.py` | 동일 |
| `tests/test_fundamental_router.py` | `AsyncMock(side_effect=ValueError("stock master not found: 005930"))` → `AsyncMock(side_effect=StockMasterNotFoundError("005930"))`. router 가 여전히 404 반환 단언 |
| `tests/test_ohlcv_router.py` | 동일 |
| `tests/test_daily_flow_router.py` | 동일 |

### 3.5 문서 (4)

- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 22 추가 (R1 결과)
- `src/backend_kiwoom/STATUS.md` 갱신 — chunk 19 누적, 다음 후보 재정렬
- `HANDOFF.md` 전체 갱신
- `CHANGELOG.md` prepend

## 4. 적대적 사전 self-check (H-1 ~ H-7)

| # | 위험 | 완화 |
|---|------|------|
| H-1 | `tuple` → JSON 직렬화 차이 | Pydantic v2 가 tuple 도 `array` 로 직렬화. OpenAPI 스키마 동일. 응답 body 변화 0 |
| H-2 | `StockMasterNotFoundError(ValueError)` 가 기존 `except ValueError` 캐치 | ValueError 상속이라 기존 caller 영향 0. 새 분기만 추가. backward compatible |
| H-3 | router `except StockMasterNotFoundError` 가 `except ValueError` 보다 먼저 와야 | Python `except` 매칭 순서 — subclass first. 코드 리뷰에서 명시 |
| H-4 | `only_market_codes max_length=2` 가 기존 운영 호출 차단 | pattern=`r"^[0-9]{1,2}$"` 가 이미 max 2 char 만 허용. max_length=4 는 dead validator. 운영 영향 0 |
| H-5 | `fetched_at: datetime | None` → `datetime` 변경 시 fixture 호환 | ORM NOT NULL + server_default 라 항상 값 존재. fixture 도 항상 채워서 호출 — 영향 0. 단 from_attributes 패턴에서 ORM 미저장 객체는 fail-fast 됨 (의도) |
| H-6 | `except Exception` 격리가 KiwoomError 외 진짜 버그를 silent 처리 | partial-failure 모델 의도 — 하나 종목 실패가 전체 sync 중단을 막아야 함. 주석으로 trade-off 명시. 로그 레벨은 WARNING 유지 (debug 가능) |
| H-7 | tuple 변경이 fundamental 의 `B-γ-2 2R` 결정 충돌 | B-γ-2 ADR (§ 14) 확인 — frozen dataclass 채택했으므로 tuple 화는 일관 강화. 충돌 없음 |

## 5. DoD (R1)

**코드** (목표: ruff/mypy strict PASS / 기존 동작 무변):
- [ ] `app/application/exceptions.py` (또는 적절한 위치) `StockMasterNotFoundError` 정의 — `stock_code: str` 속성 + `__init__` + `__str__` 안정
- [ ] 3 service `errors` field type 변경 + 내부 build-then-freeze 패턴 일관
- [ ] 3 service `raise StockMasterNotFoundError(stock_code)` 적용 (3 raise)
- [ ] 3 service `except KiwoomError` → `except Exception` (refresh_one NXT 격리 of OHLCV/daily_flow) + 주석. fundamental 은 KRX-only 라 N/A
- [ ] 3 router DTO `errors: tuple[...]`
- [ ] 3 router `only_market_codes max_length=4 → 2`
- [ ] 3 router `fetched_at: datetime` (non-Optional)
- [ ] 3 router `except StockMasterNotFoundError` 분기 추가 (subclass first)
- [ ] 기존 docstring 의 "ValueError stock master not found" 표현 갱신

**테스트** (목표: 816 → ~820 / coverage ≥ 93%):
- [ ] 3 service test 의 `pytest.raises(ValueError, match=...)` → `pytest.raises(StockMasterNotFoundError)` (M-2)
- [ ] 3 router test 의 `AsyncMock(side_effect=ValueError(...))` → `AsyncMock(side_effect=StockMasterNotFoundError(...))`. 404 응답 단언 그대로
- [ ] 신규 회귀 테스트 (선택): `test_exceptions.py` — `StockMasterNotFoundError` 가 `isinstance(_, ValueError)` 인지 (backward compat 보증)

**Verification**:
- [ ] mypy --strict 65 files 0 errors
- [ ] ruff check All passed
- [ ] pytest 전체 PASS (816 → ~820 cases)
- [ ] coverage ≥ 93%

**리뷰**:
- [ ] 1R 리뷰 PASS (refactor 분류라 2b 자동 생략 가능 / 사용자 `--force-2b` 권한)

**문서**:
- [ ] ADR § 22 추가 (R1 결과)
- [ ] CHANGELOG: `refactor(kiwoom): Phase C R1 — 3 도메인 일관 개선 (errors → tuple / StockMasterNotFoundError / LOW 3건)`
- [ ] STATUS.md 갱신 — chunk 19 누적
- [ ] HANDOFF.md 갱신
- [ ] (선택) ADR-0001 § 19.5 / § 17.4 의 Defer 표에서 해소된 항목 ✅ 마킹

## 6. 다음 chunk (R1 이후)

1. **C-3 (ka10082/83 주봉/월봉, P1)** — chart endpoint 재사용. 이번 R1 의 정리된 패턴 그대로 복제
2. **C-backfill (`scripts/backfill_*.py` CLI)** — Phase C-2 마무리. 3년 백필 시간 실측
3. **KOSCOM cross-check 수동** — 가설 B 최종 확정
4. **Phase D 진입** — ka10080 분봉 또는 ka10079 틱 (대용량 파티션 결정 선행)

---

_R1 = Refactor 1. 향후 R2/R3 은 운영 가동 후 발견되는 일관 개선 chunk 시리즈._

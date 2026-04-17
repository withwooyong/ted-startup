# Context Budget Report — VERBOSE

> 생성일: 2026-04-17 (세션 종료 시점)
> 대상: ted-startup 프로젝트 Claude Code 세션
> 모델: Claude Opus 4.7 (1M window)
> 리포트 종류: `/everything-claude-code:context-budget --verbose`

## 1. 요약

| 항목 | 값 |
|---|---|
| 총 오버헤드 (추정) | **~24,400 tokens** |
| 1M 컨텍스트 비율 | 2.44% → 975,600 여유 |
| 200K 컨텍스트 비율 (Sonnet 환산) | 12.2% → 175,600 여유 |
| 잠재 절감 (Top 1~5 적용 시) | **~4,100 tokens (17%)** |
| 최종 권고 | Opus 4.7 유지 시 액션 스킵, Sonnet 전환 계획 시 Top 1~3 적용 |

---

## 2. 컴포넌트 브레이크다운 (세션 시작 시점 로드분)

| Component | Count | Tokens |
|---|---:|---:|
| Base harness + system prompt | — | ~11,000 |
| Core tool schemas (Read/Bash/…) | ~12 | ~3,500 |
| CLAUDE.md chain | 3 | ~1,040 |
| Memory index (MEMORY.md) | 1 line | ~17 |
| User skills (descriptions) | 18 | ~720 |
| ECC plugin skills (descriptions) | ~122 | ~4,880 |
| document-skills plugin | ~17 | ~680 |
| example-skills plugin (duplicates) | ~14 | ~560 |
| Built-in commands | 3 | ~120 |
| MCP deferred tool names | ~125 | ~1,900 |
| MCP server instructions | 1 | ~30 |
| Project agents (on-demand) | 16 | 0 \* |

\* subagent-dispatch 시에만 로드됨

---

## 3. Agents (project — 현재 0 loaded, 참고용)

총 16 files / 2,181 words / ~2,835 tokens (invoke 시 비용)

| Agent | Words | Tokens | 비고 |
|---|---:|---:|---|
| `08-backend` | 293 | ~380 | 최대 |
| `07-db` | 217 | ~282 | |
| `09-frontend` | 213 | ~277 | |
| `01-biz-analyst` | 180 | ~234 | |
| `00-judge` | 131 | ~170 | |
| `00-advisor` | 129 | ~168 | |
| `13-security` | 127 | ~165 | |
| `11-qa` | 115 | ~150 | |
| `12-devops` | 113 | ~147 | |
| `06-design` | 112 | ~146 | |
| `02-pm` | 101 | ~131 | |
| `00-distiller` | 96 | ~125 | |
| `04-marketing` | 92 | ~120 | |
| `05-crm` | 91 | ~118 | |
| `10-app` | 89 | ~116 | |
| `03-planning` | 82 | ~107 | |

✅ 모두 200-line "heavy" threshold 미만. Frontmatter description 과부하 없음. **액션 없음.**

---

## 4. CLAUDE.md Chain (auto-loaded)

| File | Words | Tokens |
|---|---:|---:|
| `<project>/CLAUDE.md` | 715 | ~930 |
| `~/.claude/CLAUDE.md` | 38 | ~50 |
| `<project>/src/frontend/CLAUDE.md` | 1 | ~2 |
| `<project>/src/frontend/AGENTS.md` (via `@` 참조) | 45 | ~60 |
| **TOTAL** | **799** | **~1,040** |

### 프로젝트 CLAUDE.md 섹션 분석

| 라인 범위 | 내용 | 조치 |
|---|---|---|
| 1–35 | Overview / Getting Started / Phases | 유지 |
| 37–60 | Tech Stack / Pipeline diagram | 유지 |
| 62–80 | Agent Architecture | 유지 |
| 82–104 | Key Design Decisions + Context mgmt | ⚠️ `rules/` 분리 후보 |
| 106–117 | Backend Conventions (네이버 컨벤션) | ⚠️ `rules/java-style.md` 후보 |
| 119–127 | Frontend Conventions (토스/NHN) | ⚠️ `rules/next-style.md` 후보 |
| 129–131 | Compaction Recovery | 유지 |

프론트엔드 `@AGENTS.md` 참조 패턴은 적절. Next.js 16 breaking-change 경고는 이번 세션 `proxy.ts` 마이그레이션 판단에 실사용됨 → **유지**.

---

## 5. Skills — Top Weight Drivers (body invoke 시 비용)

### 5-1. User skills (`~/.claude/skills/`) — 현재 description 로드 ~720 tk

| Skill | Words | Tokens | 해당성 |
|---|---:|---:|---|
| python-testing-patterns | 1,050 | ~1,365 | ❌ 프로젝트 무관 |
| python-performance-optimization | 874 | ~1,136 | ❌ |
| async-python-patterns | 757 | ~984 | ❌ |
| database-migration | 433 | ~563 | ➖ 가능성 |
| python-design-patterns | 411 | ~534 | ❌ |
| python-code-style | 360 | ~468 | ❌ |
| **java-spring-boot** | 208 | ~270 | ⭐ 프로젝트 맞춤 |
| **ted-run** | 201 | ~261 | ⭐ 이번 세션 사용 |
| temporal-python-testing | 158 | ~205 | ❌ |
| **vercel-react-best-practices** | 136 | ~177 | ⭐ 프로젝트 맞춤 |
| find-skills | 133 | ~173 | ➖ 유틸 |
| vercel-composition-patterns | 89 | ~116 | ➖ 프론트 보조 |
| **handoff** | 73 | ~95 | ⭐ 이번 세션 사용 |

Python 6종 합계: ~4,690 tokens (invoke 시). **현재 부담 0**, 향후 실수 invoke 방지 대상.

### 5-2. ECC plugin 최상위 heavy (invoke 시 비용)

| Skill | Lines | Tokens | 비고 |
|---|---:|---:|---|
| kotlin-testing | 824 | ~2,145 | ❌ 비해당 스택 |
| python-testing | 816 | ~2,120 | ❌ |
| data-scraper-agent | 764 | ~1,985 | ➖ |
| python-patterns | 750 | ~1,950 | ❌ |
| django-patterns | 734 | ~1,910 | ❌ |
| django-tdd | 729 | ~1,895 | ❌ |
| cpp-coding-standards | 723 | ~1,880 | ❌ |
| golang-testing | 720 | ~1,873 | ❌ |
| kotlin-exposed-patterns | 719 | ~1,870 | ❌ |
| kotlin-patterns | 711 | ~1,850 | ❌ |

모두 프로젝트 스택(Java/Spring Boot + Next.js/TypeScript) 외 → **0 utility**.

---

## 6. MCP — Deferred Tool Inventory (~125 tools)

| Server | Tools | Names tk (loaded) | Schemas (deferred) |
|---|---:|---:|---|
| (built-in agent tools) | ~23 | ~345 | on-fetch |
| atlassian (basic) | 8 | ~120 | on-fetch |
| claude_ai_Atlassian_Rovo | ~38 | ~570 | ❌ 미사용 |
| claude_ai_Gmail | 8 | ~120 | ❌ 미사용 |
| claude_ai_Google_Calendar | 8 | ~120 | ❌ 미사용 |
| claude_ai_Google_Drive | 7 | ~105 | ❌ 미사용 |
| claude_ai_Notion | 13 | ~195 | ❌ 미사용 |
| claude_ai_Slack | 14 | ~210 | ❌ 미사용 |
| ide | 2 | ~30 | (VS Code diag) |
| **TOTAL** | **~125** | **~1,815** | ~62,500 if all fetched |

Deferred schemas은 tool당 ~500 tk × 125 ≈ **62,500 tokens potential**. 이번 세션은 `TaskCreate/Update/List`만 fetch (~1,500 tk). Claude Code의 deferred-fetch 구조 덕에 **실효 오버헤드는 낮음**.

---

## 7. 발견된 이슈 (6건)

### Issue 1 — MCP Over-Subscription (MEDIUM)

7개 외부 MCP 서버가 활성화되어 있으나 이 프로젝트에서 직접 사용 없음.
(Gmail / GCal / GDrive / Notion / Slack / Atlassian Rovo / Atlassian 기본)

- **현재 비용**: 이름만 ~1,380 tokens
- **잠재 비용**: 실수 invoke 시 tool당 ~500 tokens — Rovo 1건만 불러도 **+18,500 tokens**
- **Savings**: ~1,380 tokens + 실수 invoke 방지

### Issue 2 — Plugin 중복 (LOW)

`example-skills` 14개는 모두 `document-skills` 17개의 서브셋(동일 SKILL.md 복사).

예: `example-skills:xlsx ≡ document-skills:xlsx` (동일 해시)

- **Savings**: ~560 tokens (descriptions 제거)

### Issue 3 — 스택 비해당 skill 군집 (MEDIUM)

Project stack: Java/Spring Boot + Next.js 16/TypeScript

활용 0 skills (총 ~38개):

| 카테고리 | 개수 | 목록 |
|---|---:|---|
| Kotlin | 6 | kotlin-patterns, kotlin-testing, kotlin-ktor-patterns, kotlin-exposed-patterns, kotlin-coroutines-flows, compose-multiplatform-patterns |
| Swift | 6 | swift-actor-persistence, swift-concurrency-6-2, swift-protocol-di-testing, swiftui-patterns, liquid-glass-design, foundation-models-on-device |
| Rust | 2 | rust-patterns, rust-testing |
| Perl | 3 | perl-patterns, perl-testing, perl-security |
| C++ | 2 | cpp-coding-standards, cpp-testing |
| Go | 2 | golang-patterns, golang-testing |
| Laravel | 4 | laravel-patterns, laravel-security, laravel-tdd, laravel-verification |
| Django | 4 | django-patterns, django-security, django-tdd, django-verification |
| Flutter | 1 | flutter-dart-code-review |
| Domain-specific | 8 | logistics / customs / energy / scheduling / inventory 등 |

- **Savings**: ~1,520 tokens (description 제거) + skill picker 가독성 개선

### Issue 4 — User skills Python 편중 (LOW)

18개 user skill 중 6개가 Python. 현재 프로젝트는 Python 없음.

- **Description 로드만**: ~240 tokens
- **Body invoke 시**: ~4,690 tokens
- 다른 Python 프로젝트가 있다면 유지, 아니면 이동/제거
- **Savings**: ~240 tokens (description) + future-invoke 안전성

### Issue 5 — CLAUDE.md 스타일 블록 rules화 가능 (LOW)

프로젝트 CLAUDE.md 82~127행(46행, ~450 tk)이 Java/Next 스타일 컨벤션.
ECC `rules-distill` skill로 `rules/java-style.md` + `rules/next-style.md` 분리 가능.

- **Savings**: ~400 tokens (CLAUDE.md는 매 세션 자동 로드, rules는 invoke 시만)

### Issue 6 — tool search noise (INFO)

`/context-budget` 스킬 자체가 실행 중 ~4 KB 지시문 로드. 정상. **액션 없음.**

---

## 8. Top Optimizations (우선순위)

| # | 조치 | 예상 절감 | 리스크 |
|---|---|---:|---|
| 1 | Unused MCP 서버 6종 비활성화 (Gmail/GCal/GDrive/Notion/Slack/Atlassian-Rovo) | ~1,380 tk (+Rovo 잠재 -18,500) | 낮음 — 이 프로젝트에서 미사용 확인됨 |
| 2 | 비해당 스택 ECC skill 38종 제거 (Kotlin/Swift/Rust/Perl/C++/Go/Laravel/Django/Flutter/Domain) | ~1,520 tk | 낮음 — 본 프로젝트 전용이면 안전 |
| 3 | `example-skills` plugin 제거 (document-skills 중복) | ~560 tk | 매우 낮음 |
| 4 | CLAUDE.md 스타일 블록 → `rules/*.md` 분리 | ~400 tk | 중 — rules 인덱싱 확인 필요 |
| 5 | User Python skill군 별도 프로필로 격리 | ~240 tk | 중 — 다른 Python 프로젝트 영향 확인 |

**누적 잠재 savings**: ~4,100 tokens (~17% of current overhead)

**After optimization**:

- 1M scale: 2.03% → 979,700 effective (체감 차이 없음)
- 200K scale: 10.2% → 179,700 effective (Sonnet 전환 시 의미 있음)

---

## 9. 권고

### 현 세션 (Opus 4.7 유지)

- **액션 스킵 권장**. Overhead 2.44%는 무시 가능 수준.
- 다만 **Issue 1 (MCP Rovo 비활성화)**만 선제 처리하면 실수 invoke 리스크 제거 (+품질 안정).

### Sonnet / Haiku 전환 계획이 있을 때

- Top 1~3 일괄 적용 (15~20분 작업). 4,100 tk 회수.

### 도구

- **스킬 정리**: `/everything-claude-code:configure-ecc` — 설치 스킬 선별
- **MCP 정리**: Claude Code `settings.json` 에서 `mcpServers` 블록 축소 또는 `/config` 메뉴
- **자동화**: ECC의 `skill-stocktake`, `rules-distill` 스킬이 정리 작업을 반자동화

---

## 10. 핵심 결론

- **현 세션 오버헤드 ~24.4K tokens (1M 중 2.4%)** — Opus 4.7에서는 무시 가능.
- **가장 큰 비효율은 "스킬 description 로드 vs 실제 사용 비율"**. 175개 중 이번 세션 사용은 10개 내외.
- **"잠복 위험"은 MCP Rovo 서버** — 38개 tool schema를 실수로 fetch하면 18K+ 토큰 부담. 사용 안 하면 비활성화 권장.
- **Sonnet 전환 계획이 없다면 Top 1만 적용**(MCP 정리) — 나머지는 투자 대비 효과 작음.

---
allowed-tools: Bash, Read, Write
description: 코드 리뷰 + 보안 검증만 실행
---

# Code Review + Security Audit

## Step 1: 소스코드 확인
- `src/backend/` 소스코드 존재 확인
- `src/frontend/` 소스코드 존재 확인

## Step 2: 에이전트 실행
1. `agents/08-backend/AGENT.md` (review mode) → 코드 리뷰
   - SOLID 원칙, 보안 취약점, 성능 이슈, 에러 핸들링, 테스트 커버리지
2. `agents/13-security/AGENT.md` → 보안 검증
   - OWASP Top 10, 의존성 취약점, Security Headers

## Step 3: 리포트 생성
- `pipeline/artifacts/08-review-report/review.md`
- `pipeline/artifacts/09-security-audit/audit-report.md`

## Step 4: 사용자 보고
코드 리뷰 + 보안 검증 결과 요약

# 에이전트 간 컨텍스트 전달 프로토콜

## 원칙
1. 모든 에이전트 산출물은 마크다운 + YAML 프론트매터
2. 다음 에이전트는 이전 산출물 파일을 직접 읽음
3. 변경사항은 changelog 섹션에 기록

## 산출물 표준 헤더
```yaml
---
agent: "agent-name"
stage: "01-requirements"
version: "1.0.0"
created_at: "ISO-8601"
depends_on:
  - "pipeline/artifacts/..."
quality_gate_passed: false
changelog:
  - version: "1.0.0"
    changes: "Initial creation"
---
```

## 핸드오프 체크리스트
- [ ] 산출물 스키마 준수
- [ ] 이전 단계 산출물과 일관성
- [ ] 품질 게이트 체크리스트 통과
- [ ] quality_gate_passed를 true로 변경

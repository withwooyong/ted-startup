# === 1. 핵심 파일 존재 확인 ===
echo "=== 필수 파일 ==="
[ -f CLAUDE.md ] && echo "✅ CLAUDE.md ($(wc -l < CLAUDE.md) 줄)" || echo "❌ CLAUDE.md 없음"
[ -f .claude/settings.json ] && echo "✅ settings.json" || echo "❌ settings.json 없음"
[ -f .gitignore ] && echo "✅ .gitignore" || echo "❌ .gitignore 없음"

# === 2. 에이전트 수 확인 ===
echo ""
echo "=== 에이전트 ==="
AGENT_COUNT=$(find agents -name "AGENT.md" 2>/dev/null | wc -l | tr -d ' ')
echo "AGENT.md 파일: $AGENT_COUNT / 16"

# 누락된 에이전트 찾기
for agent in 00-distiller 00-judge 00-advisor 01-biz-analyst 02-pm 03-planning 04-marketing 05-crm 06-design 07-db 08-backend 09-frontend 10-app 11-qa 12-devops 13-security; do
  [ -f "agents/$agent/AGENT.md" ] && echo "  ✅ $agent" || echo "  ❌ $agent 누락"
done

# === 3. 슬래시 커맨드 확인 ===
echo ""
echo "=== 슬래시 커맨드 ==="
for cmd in kickoff plan design develop test review deploy; do
  [ -f ".claude/commands/${cmd}.md" ] && echo "  ✅ /${cmd}" || echo "  ❌ /${cmd} 누락"
done

# === 4. 파이프라인 인프라 확인 ===
echo ""
echo "=== 파이프라인 인프라 ==="
[ -f pipeline/state/current-state.json ] && echo "✅ current-state.json" || echo "❌ 누락"
[ -f pipeline/decisions/decision-registry.md ] && echo "✅ decision-registry.md" || echo "❌ 누락"
[ -d pipeline/artifacts ] && echo "✅ artifacts 디렉토리" || echo "❌ 누락"

# === 5. 프로젝트명 치환 확인 ===
echo ""
echo "=== 프로젝트명 치환 ==="
if grep -q "ted-startup" CLAUDE.md 2>/dev/null; then
  echo "✅ 프로젝트명 CLAUDE.md에 반영됨"
else
  echo "⚠️  프로젝트명 미반영 (수동 수정 필요)"
fi

# === 6. 디렉토리 트리 ===
echo ""
echo "=== 전체 구조 ==="
tree -L 2 -I 'node_modules|.git' 2>/dev/null || find . -maxdepth 2 -type d -not -path '*/\.*' | sort
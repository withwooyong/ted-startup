#!/usr/bin/env bash
# Lighthouse 모바일 자동 측정 — 모바일 반응형 Gate 3 증빙 수집용
#
# 사전 조건 (직접 띄워야 하는 것):
#   1) backend — `cd src/backend_py && uv run uvicorn src.app.main:app --port 8000`
#   2) frontend — `cd src/frontend && yarn build && yarn start`  (production 모드)
#   3) 로그인 세션 쿠키 — portfolio/settings 같은 보호 페이지 측정 시 수동 로그인 필요
#
# 사용:
#   ./scripts/lighthouse-mobile.sh                      # 7 페이지 전체 측정
#   ./scripts/lighthouse-mobile.sh / /backtest          # 인자 지정 시 해당 경로만
#
# 결과:
#   lighthouse-reports/<slug>.{html,report.json}        # 상세 리포트
#   lighthouse-reports/summary.md                       # 스코어 요약 (paste-ready)
#
# 주의:
#   - `npx lighthouse` 첫 실행은 패키지 다운로드로 20~30s 소요
#   - `--chrome-flags='--headless=new'` 로 UI 없이 실행
#   - Performance 는 네트워크/CPU 쓰로틀링(모바일 4G) 이 기본. 일관된 값 얻으려면 노트북 전원 연결 권장
set -euo pipefail

BASE_URL="${LIGHTHOUSE_BASE_URL:-http://localhost:3000}"
OUT_DIR="${LIGHTHOUSE_OUT_DIR:-./lighthouse-reports}"

DEFAULT_PATHS=(
  "/"
  "/portfolio"
  "/stocks/005930"
  "/reports/005930"
  "/portfolio/1/alignment"
  "/backtest"
  "/settings"
)

if [[ $# -gt 0 ]]; then
  PATHS=("$@")
else
  PATHS=("${DEFAULT_PATHS[@]}")
fi

mkdir -p "$OUT_DIR"

# slug: "/" → "root", "/stocks/005930" → "stocks-005930"
slugify() {
  local path="$1"
  if [[ "$path" == "/" ]]; then
    echo "root"
  else
    echo "${path:1}" | tr '/' '-'
  fi
}

SUMMARY_FILE="$OUT_DIR/summary.md"
{
  echo "# Lighthouse 모바일 스코어 요약"
  echo ""
  echo "- 측정일: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "- Base URL: $BASE_URL"
  echo ""
  echo "| 페이지 | Performance | Accessibility | Best Practices | SEO |"
  echo "|---|---:|---:|---:|---:|"
} > "$SUMMARY_FILE"

for p in "${PATHS[@]}"; do
  slug=$(slugify "$p")
  url="${BASE_URL%/}${p}"
  echo ""
  echo "▶ [$slug] $url"

  npx --yes lighthouse "$url" \
    --quiet \
    --only-categories=performance,accessibility,best-practices,seo \
    --output=html \
    --output=json \
    --output-path="$OUT_DIR/$slug" \
    --chrome-flags='--headless=new --no-sandbox' \
    || { echo "  ✗ 측정 실패: $url"; continue; }

  # JSON 에서 4개 카테고리 점수 추출 (0~1 → 0~100 반올림)
  json="$OUT_DIR/$slug.report.json"
  if [[ -f "$json" ]]; then
    perf=$(node -e "console.log(Math.round(require('$json').categories.performance.score*100))")
    a11y=$(node -e "console.log(Math.round(require('$json').categories.accessibility.score*100))")
    bp=$(node -e "console.log(Math.round(require('$json').categories['best-practices'].score*100))")
    seo=$(node -e "console.log(Math.round(require('$json').categories.seo.score*100))")
    echo "  ✓ Perf=$perf  A11y=$a11y  BP=$bp  SEO=$seo"
    echo "| \`$p\` | $perf | $a11y | $bp | $seo |" >> "$SUMMARY_FILE"
  fi
done

echo ""
echo "===================="
echo "Summary: $SUMMARY_FILE"
echo "HTML reports: $OUT_DIR/*.html"
cat "$SUMMARY_FILE"

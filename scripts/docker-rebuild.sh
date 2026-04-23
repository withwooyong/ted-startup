#!/usr/bin/env bash
# =============================================================================
# docker-rebuild.sh — 안전한 재빌드 + 자동 정리 스크립트
# -----------------------------------------------------------------------------
# 용도: docker compose up --build 을 감싸서, 이전 빌드가 남긴 dangling 이미지와
#       빌드 캐시를 매번 자동 회수. 볼륨(DB 데이터)은 절대 건드리지 않음.
#
# 사용법:
#   ./scripts/docker-rebuild.sh                # docker-compose.prod.yml 로 재빌드
#   ./scripts/docker-rebuild.sh dev            # docker-compose.yml (로컬 DB만)
#   ./scripts/docker-rebuild.sh prod backend   # prod 스택에서 backend 만 재빌드
#
# 환경변수:
#   KEEP_CACHE_GB=5   BuildKit 캐시 보존 상한 (기본 5GB)
#   ENV_FILE          compose 변수 interpolation 용 env 파일 경로 override.
#                     prod 기본: `.env.prod` / dev 기본: `.env` (존재 시 자동).
#                     예) ENV_FILE=.env.staging ./scripts/docker-rebuild.sh prod
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."

MODE="${1:-prod}"
SERVICE="${2:-}"
KEEP_CACHE_GB="${KEEP_CACHE_GB:-5}"

case "$MODE" in
  prod)
    COMPOSE_FILE="docker-compose.prod.yml"
    ENV_FILE="${ENV_FILE:-.env.prod}"
    ;;
  dev)
    COMPOSE_FILE="docker-compose.yml"
    ENV_FILE="${ENV_FILE:-.env}"
    ;;
  *)
    echo "❌ 알 수 없는 모드: $MODE (prod|dev 중 하나)" >&2
    exit 1
    ;;
esac

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "❌ $COMPOSE_FILE 이 없습니다." >&2
  exit 1
fi

# env-file 은 존재할 때만 주입한다. prod 에서 .env.prod 미존재는 치명적이므로 에러.
# dev 의 기본 .env 는 없어도 무방 — compose 파일 자체에 env_file 지시어가 있을 수 있음.
ENV_ARGS=()
if [[ -f "$ENV_FILE" ]]; then
  ENV_ARGS=(--env-file "$ENV_FILE")
  echo "▶ env 파일: $ENV_FILE"
elif [[ "$MODE" == "prod" ]]; then
  echo "❌ prod 모드인데 env 파일 $ENV_FILE 이 없습니다." >&2
  echo "   (override: ENV_FILE=<path> ./scripts/docker-rebuild.sh prod)" >&2
  exit 1
else
  echo "▶ env 파일: (없음 — compose 파일 내부 env_file 지시어에 위임)"
fi

echo "▶ 사용 compose 파일: $COMPOSE_FILE"
echo "▶ 재빌드 대상: ${SERVICE:-<전체 서비스>}"
echo

# -----------------------------------------------------------------------------
# 1) 기존 스택 정지 (볼륨은 보존)
# -----------------------------------------------------------------------------
echo "▶ [1/4] docker compose down (볼륨 보존)"
docker compose "${ENV_ARGS[@]}" -f "$COMPOSE_FILE" down --remove-orphans

# -----------------------------------------------------------------------------
# 2) 재빌드 (캐시는 활용, 그러나 이전 이미지 태그는 덮어쓰여 dangling 됨)
# -----------------------------------------------------------------------------
echo "▶ [2/4] docker compose build"
if [[ -n "$SERVICE" ]]; then
  docker compose "${ENV_ARGS[@]}" -f "$COMPOSE_FILE" build "$SERVICE"
else
  docker compose "${ENV_ARGS[@]}" -f "$COMPOSE_FILE" build
fi

# -----------------------------------------------------------------------------
# 3) 정리: dangling 이미지 + 초과 빌드 캐시 (볼륨은 절대 안 건드림)
# -----------------------------------------------------------------------------
echo "▶ [3/4] 정리: dangling 이미지 + 빌드 캐시 (>${KEEP_CACHE_GB}GB)"

# 이전 빌드가 남긴 <none> 태그 이미지만 정확히 제거
DANGLING=$(docker images -f "dangling=true" -q | wc -l | tr -d ' ')
if [[ "$DANGLING" -gt 0 ]]; then
  echo "  - dangling 이미지 ${DANGLING}개 제거"
  docker image prune -f >/dev/null
else
  echo "  - dangling 이미지 없음"
fi

# BuildKit 캐시가 KEEP_CACHE_GB 초과분만 잘라냄
echo "  - builder 캐시를 ${KEEP_CACHE_GB}GB 이하로 유지"
docker builder prune -f --keep-storage "${KEEP_CACHE_GB}GB" >/dev/null || true

# -----------------------------------------------------------------------------
# 4) 기동
# -----------------------------------------------------------------------------
echo "▶ [4/4] docker compose up -d"
docker compose "${ENV_ARGS[@]}" -f "$COMPOSE_FILE" up -d

echo
echo "✅ 완료"
docker system df

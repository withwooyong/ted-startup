#!/usr/bin/env bash
# =============================================================================
# docker-clean.sh — 수동 Docker 디스크 정리 (볼륨은 보호)
# -----------------------------------------------------------------------------
# 용도: 주기적으로 (또는 디스크 부족 시) 실행해서 안 쓰는 이미지/캐시 제거.
#       --volumes 플래그는 **의도적으로 제외** — Postgres 데이터 보호.
#
# 사용법:
#   ./scripts/docker-clean.sh          # 안전 모드 (dangling 만)
#   ./scripts/docker-clean.sh --deep   # 참조 안 되는 모든 이미지까지 (컨테이너 정지 필요)
# =============================================================================
set -euo pipefail

MODE="${1:-safe}"

echo "▶ 정리 전 상태"
docker system df
echo

case "$MODE" in
  safe|"")
    echo "▶ [안전 모드] dangling 이미지 + 중지된 컨테이너 + 미사용 네트워크 + 빌드 캐시"
    docker system prune -f
    ;;
  --deep|deep)
    echo "⚠  [딥 클린] 실행 중인 컨테이너에서 참조 안 되는 모든 이미지까지 제거합니다."
    echo "    (볼륨은 건드리지 않음 — DB 데이터 안전)"
    read -rp "계속? [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] || { echo "중단."; exit 0; }
    docker system prune -af
    ;;
  *)
    echo "사용법: $0 [--deep]" >&2
    exit 1
    ;;
esac

echo
echo "✅ 정리 후 상태"
docker system df

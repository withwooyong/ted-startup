# syntax=docker/dockerfile:1.7
# =============================================================================
# 프론트엔드 멀티스테이지 Dockerfile (Next.js 16 + React 19)
# =============================================================================
# Stage 1: deps      — package.json 기반 node_modules 설치 (캐시 분리)
# Stage 2: builder   — next build (output: standalone) 수행
# Stage 3: runtime   — node 20-slim + standalone 산출물만 복사
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: 의존성 설치 (캐시 레이어)
# -----------------------------------------------------------------------------
FROM node:20-slim AS deps
WORKDIR /app

# package.json + lock 을 우선 복사하여 변경시에만 재설치
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# -----------------------------------------------------------------------------
# Stage 2: Next.js 빌드
# -----------------------------------------------------------------------------
FROM node:20-slim AS builder
WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# next.config.ts 에 output: 'standalone' 설정 필요 (이미 적용됨)
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 3: 런타임 (경량)
# -----------------------------------------------------------------------------
FROM node:20-slim AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# 비루트 유저 준비
RUN groupadd --system --gid 1001 nodejs \
 && useradd --system --uid 1001 --gid nodejs nextjs

# standalone 빌드 산출물 (minimum runtime + 의존성 포함)
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

EXPOSE 3000

# standalone 번들은 루트의 server.js 를 엔트리포인트로 사용
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD node -e "fetch('http://localhost:3000/').then(r => { if (!r.ok) process.exit(1); }).catch(() => process.exit(1))"

CMD ["node", "server.js"]

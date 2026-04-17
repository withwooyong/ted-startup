# syntax=docker/dockerfile:1.7
# =============================================================================
# 백엔드 멀티스테이지 Dockerfile (Spring Boot 3.5 + Java 21)
# =============================================================================
# Stage 1: build — Gradle + JDK 21 Temurin 으로 bootJar 생성
# Stage 2: runtime — JRE 21 slim 이미지로 얇게 패키징
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder
# -----------------------------------------------------------------------------
FROM eclipse-temurin:21-jdk-jammy AS builder

WORKDIR /workspace

# Gradle 래퍼 + 의존성 매니페스트 먼저 복사하여 의존성 캐시 활용
COPY gradlew ./
COPY gradle ./gradle
COPY build.gradle settings.gradle ./

# 래퍼 실행권한 확보 후 의존성만 선다운로드 (소스 변경해도 캐시 재사용)
RUN chmod +x gradlew \
 && ./gradlew --no-daemon dependencies || true

# 소스 복사 후 bootJar 빌드 (테스트는 CI에서 별도 수행)
COPY src ./src
RUN ./gradlew --no-daemon clean bootJar -x test

# -----------------------------------------------------------------------------
# Stage 2: Runtime
# -----------------------------------------------------------------------------
FROM eclipse-temurin:21-jre-jammy AS runtime

# 비루트 유저 (UID 1001) 로 실행 — 보안 하드닝
RUN groupadd --system --gid 1001 spring \
 && useradd --system --uid 1001 --gid spring --no-create-home spring

WORKDIR /app

# curl 은 healthcheck 용으로만 설치 (최소 surface)
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# bootJar 복사
COPY --from=builder --chown=spring:spring /workspace/build/libs/*.jar /app/app.jar

USER spring:spring

EXPOSE 8080

# Spring Actuator /actuator/health 를 이용한 헬스체크
# (build.gradle 에 spring-boot-starter-actuator 포함 확인)
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
  CMD curl -fsS http://localhost:8080/actuator/health | grep -q '"status":"UP"' || exit 1

# JVM 컨테이너 인지 옵션 + Virtual Thread 친화 GC 설정
ENV JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0 -Djava.security.egd=file:/dev/./urandom"

ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/app.jar"]

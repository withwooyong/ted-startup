import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 프로덕션 Docker 이미지용 standalone 출력 (next/server 런타임만 포함하는 최소 번들)
  output: "standalone",
  // /api/* → backend 프록시는 next.config.ts rewrites 대신 middleware.ts에서 처리한다.
  // 이유: rewrites는 next build 시점에 routes-manifest.json에 고정되므로 런타임 env(BACKEND_INTERNAL_URL)
  //       값이 이미지에 baked되는 문제가 있다. middleware는 매 요청 평가이므로 컨테이너 env로 제어 가능.
};

export default nextConfig;

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 프로덕션 Docker 이미지용 standalone 출력 (next/server 런타임만 포함하는 최소 번들)
  output: "standalone",
};

export default nextConfig;

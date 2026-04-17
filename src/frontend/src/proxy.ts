import { NextResponse, type NextRequest } from 'next/server';

/**
 * 브라우저의 /api/* 요청을 내부 네트워크의 backend 로 프록시한다.
 * - /api/admin/* 는 별도 Route Handler(서버 전용 ADMIN_API_KEY 사용)가 처리하므로 통과.
 * - 나머지 /api/* 는 backend 로 rewrite (URL은 브라우저에게 보이지 않음, 같은 origin 유지).
 *
 * 왜 next.config.ts rewrites 대신 proxy?
 * → rewrites 는 next build 시점에 routes-manifest.json 으로 고정되어 런타임 env 를 반영하지 못한다.
 *   proxy 는 서버 기동 시 process.env 를 읽으므로 compose runtime 의 BACKEND_INTERNAL_URL 이 유효.
 *
 * Next.js 16에서 middleware 파일 컨벤션이 proxy 로 개명됨.
 */
export function proxy(req: NextRequest) {
  const { pathname, search } = req.nextUrl;

  // Route Handler 우선
  if (pathname.startsWith('/api/admin/')) {
    return NextResponse.next();
  }

  if (pathname.startsWith('/api/')) {
    const backend = process.env.BACKEND_INTERNAL_URL || 'http://localhost:8080';
    return NextResponse.rewrite(new URL(pathname + search, backend));
  }

  return NextResponse.next();
}

export const config = {
  matcher: '/api/:path*',
};

import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// 서버 사이드 전용 env — compose에서 BACKEND_INTERNAL_URL=http://backend:8080 주입
const BACKEND_BASE = process.env.BACKEND_INTERNAL_URL || 'http://localhost:8080';

// 관리자 preferences 페이로드는 수백 바이트 수준. 16KB 상한으로 DoS/오동작 페이로드 방어.
const MAX_BODY_BYTES = 16 * 1024;

/**
 * 관리자 API Key를 서버 측에서만 보관하기 위한 릴레이 라우트.
 * 브라우저에서 직접 백엔드를 호출할 때 NEXT_PUBLIC_ 프리픽스로 키가 번들에 인라인되는 문제를 해결한다.
 * 클라이언트는 이 경로로 요청하고, 서버가 ADMIN_API_KEY 환경변수를 X-API-Key 헤더로 붙여 백엔드에 전달.
 */
export async function PUT(req: NextRequest) {
  const apiKey = process.env.ADMIN_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { status: 500, message: '서버에 ADMIN_API_KEY가 설정되지 않았습니다' },
      { status: 500 },
    );
  }

  const contentLength = Number(req.headers.get('content-length') ?? '0');
  if (contentLength > MAX_BODY_BYTES) {
    return NextResponse.json(
      { status: 413, message: '요청 본문이 너무 큽니다' },
      { status: 413 },
    );
  }

  const body = await req.text();
  if (body.length > MAX_BODY_BYTES) {
    return NextResponse.json(
      { status: 413, message: '요청 본문이 너무 큽니다' },
      { status: 413 },
    );
  }

  const upstream = await fetch(`${BACKEND_BASE}/api/notifications/preferences`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
    },
    body,
    cache: 'no-store',
  });

  const text = await upstream.text();
  const contentType = upstream.headers.get('content-type') ?? 'application/json';
  return new NextResponse(text, {
    status: upstream.status,
    headers: { 'Content-Type': contentType },
  });
}

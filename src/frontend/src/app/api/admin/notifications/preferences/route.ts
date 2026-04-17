import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const BACKEND_BASE =
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'http://localhost:8080/api';

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

  const body = await req.text();

  const upstream = await fetch(`${BACKEND_BASE}/notifications/preferences`, {
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

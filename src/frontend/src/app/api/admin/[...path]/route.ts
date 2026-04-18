import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// 서버 사이드 전용 env — compose에서 BACKEND_INTERNAL_URL=http://backend:8000 주입
const BACKEND_BASE = process.env.BACKEND_INTERNAL_URL || 'http://localhost:8000';

// 요청 본문 크기 상한 — /api/admin/reports 같은 큰 페이로드는 없지만 DoS 방어.
const MAX_BODY_BYTES = 64 * 1024;

/**
 * 관리자 API Key를 서버 측에서만 보관하기 위한 제네릭 릴레이.
 *
 * 브라우저의 /api/admin/<...path> 요청을 받아 ADMIN_API_KEY 헤더를 붙여
 * 백엔드의 같은 경로(단 'admin/' 접두 제거)로 포워드한다.
 *
 * 매핑 규칙:
 *   /api/admin/portfolio/accounts           → /api/portfolio/accounts
 *   /api/admin/portfolio/accounts/1/sync    → /api/portfolio/accounts/1/sync
 *   /api/admin/reports/005930               → /api/reports/005930
 *
 * 왜 기존 preferences 라우트 대신 이 catch-all 을 도입했나
 * → P14 에서 portfolio·reports 등 관리자 보호 엔드포인트가 10개 이상으로 늘어
 *   per-endpoint 라우트 파일을 두는 비용이 커졌기 때문. 단, 기존 notifications/
 *   preferences 라우트는 하위 호환으로 유지하되 추가 엔드포인트는 여기서 처리.
 */

async function relay(
  req: NextRequest,
  path: string[],
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH',
): Promise<NextResponse> {
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

  // query string 포함 URL 재구성. 경로 prefix 는 /api/ 로 교체.
  const search = req.nextUrl.searchParams.toString();
  const targetPath = `/api/${path.join('/')}`;
  const upstreamUrl = `${BACKEND_BASE}${targetPath}${search ? `?${search}` : ''}`;

  const headers: Record<string, string> = {
    'X-API-Key': apiKey,
  };
  const contentType = req.headers.get('content-type');
  if (contentType) headers['Content-Type'] = contentType;

  let body: string | undefined;
  if (method !== 'GET' && method !== 'DELETE') {
    body = await req.text();
    if (body.length > MAX_BODY_BYTES) {
      return NextResponse.json(
        { status: 413, message: '요청 본문이 너무 큽니다' },
        { status: 413 },
      );
    }
  }

  const upstream = await fetch(upstreamUrl, {
    method,
    headers,
    body,
    cache: 'no-store',
  });

  const text = await upstream.text();
  const respContentType = upstream.headers.get('content-type') ?? 'application/json';
  return new NextResponse(text, {
    status: upstream.status,
    headers: { 'Content-Type': respContentType },
  });
}

type Params = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, { params }: Params) {
  const { path } = await params;
  return relay(req, path, 'GET');
}

export async function POST(req: NextRequest, { params }: Params) {
  const { path } = await params;
  return relay(req, path, 'POST');
}

export async function PUT(req: NextRequest, { params }: Params) {
  const { path } = await params;
  return relay(req, path, 'PUT');
}

export async function DELETE(req: NextRequest, { params }: Params) {
  const { path } = await params;
  return relay(req, path, 'DELETE');
}

export async function PATCH(req: NextRequest, { params }: Params) {
  const { path } = await params;
  return relay(req, path, 'PATCH');
}

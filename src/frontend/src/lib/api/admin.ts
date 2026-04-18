// 관리자 보호 엔드포인트의 공통 베이스. Next.js Route Handler(/api/admin/[...path]) 가
// 서버 측에서 ADMIN_API_KEY 를 부착한다. 절대 NEXT_PUBLIC 변수로 노출되지 않도록
// 여기서는 경로 상수만 관리.
export const ADMIN_BASE = '/api/admin';

export async function adminCall<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${ADMIN_BASE}${path}`, {
    ...init,
    cache: 'no-store',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as {
      message?: string;
      detail?: string;
    };
    const msg = body.message || body.detail || `API Error: ${res.status}`;
    const err = new Error(msg) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return (await res.json()) as T;
}

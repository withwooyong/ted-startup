import type { LatestSignalsResult, SignalResult, StockDetail, BacktestSummary } from '@/types/signal';
import type {
  NotificationPreference,
  NotificationPreferenceUpdate,
} from '@/types/notification';

// 브라우저에서는 상대 경로 '/api'를 사용해 Next.js 서버의 rewrites가 backend로 프록시한다.
// 개발 환경에서 별도 도메인 백엔드를 쓰고 싶으면 NEXT_PUBLIC_API_BASE_URL을 설정.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || '/api';

async function fetchApi<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    cache: 'no-store',
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.message || `API Error: ${res.status}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function getSignals(date?: string, type?: string): Promise<SignalResult[]> {
  const params = new URLSearchParams();
  if (date) params.set('date', date);
  if (type) params.set('type', type);
  const query = params.toString();
  return fetchApi<SignalResult[]>(`/signals${query ? `?${query}` : ''}`);
}

export async function getLatestSignals(type?: string): Promise<LatestSignalsResult> {
  const params = new URLSearchParams();
  if (type) params.set('type', type);
  const query = params.toString();
  return fetchApi<LatestSignalsResult>(`/signals/latest${query ? `?${query}` : ''}`);
}

export async function getStockDetail(
  code: string,
  from?: string,
  to?: string,
  options?: { signal?: AbortSignal }
): Promise<StockDetail> {
  const params = new URLSearchParams();
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  const query = params.toString();
  return fetchApi<StockDetail>(
    `/stocks/${code}${query ? `?${query}` : ''}`,
    options?.signal ? { signal: options.signal } : undefined
  );
}

export async function getBacktestResults(): Promise<BacktestSummary[]> {
  return fetchApi<BacktestSummary[]>('/backtest');
}

export async function getNotificationPreferences(): Promise<NotificationPreference> {
  return fetchApi<NotificationPreference>('/notifications/preferences');
}

export async function updateNotificationPreferences(
  preferences: NotificationPreferenceUpdate,
): Promise<NotificationPreference> {
  // Next.js Route Handler를 경유해 서버 측 ADMIN_API_KEY로 릴레이한다.
  // 클라이언트 번들에는 관리자 키가 포함되지 않는다.
  const res = await fetch('/api/admin/notifications/preferences', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(preferences),
    cache: 'no-store',
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.message || `API Error: ${res.status}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return res.json();
}

import type { SignalResult, StockDetail, BacktestSummary } from '@/types/signal';
import type {
  NotificationPreference,
  NotificationPreferenceUpdate,
} from '@/types/notification';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api';

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

export async function getStockDetail(code: string, from?: string, to?: string): Promise<StockDetail> {
  const params = new URLSearchParams();
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  const query = params.toString();
  return fetchApi<StockDetail>(`/stocks/${code}${query ? `?${query}` : ''}`);
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

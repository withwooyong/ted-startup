import type { SignalResult, StockDetail, BacktestSummary } from '@/types/signal';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api';

async function fetchApi<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: 'no-store',
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.message || `API Error: ${res.status}`);
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

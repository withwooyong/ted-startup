// AI 분석 리포트 API — 관리자 키 보호 경로(/api/admin/reports/...).
import type { AnalysisReportResponse } from '@/types/report';

const ADMIN_BASE = '/api/admin';

export async function generateReport(
  stockCode: string,
  forceRefresh = false,
): Promise<AnalysisReportResponse> {
  const q = forceRefresh ? '?force_refresh=true' : '';
  const res = await fetch(`${ADMIN_BASE}/reports/${stockCode}${q}`, {
    method: 'POST',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { message?: string; detail?: string };
    const msg = body.message || body.detail || `API Error: ${res.status}`;
    const err = new Error(msg) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return (await res.json()) as AnalysisReportResponse;
}

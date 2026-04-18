// AI 분석 리포트 API — 관리자 키 보호 경로(/api/admin/reports/...).
import { adminCall } from '@/lib/api/admin';
import type { AnalysisReportResponse } from '@/types/report';

export async function generateReport(
  stockCode: string,
  forceRefresh = false,
): Promise<AnalysisReportResponse> {
  const q = forceRefresh ? '?force_refresh=true' : '';
  return adminCall<AnalysisReportResponse>(`/reports/${stockCode}${q}`, {
    method: 'POST',
  });
}

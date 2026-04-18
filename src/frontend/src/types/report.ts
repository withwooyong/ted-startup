export type ReportOpinion = 'BUY' | 'HOLD' | 'SELL' | 'NEUTRAL';
export type ReportSourceType = 'dart' | 'krx' | 'ecos' | 'news' | 'official';

export interface ReportSourceItem {
  tier: 1 | 2;
  type: ReportSourceType;
  url: string;
  label: string;
  published_at: string | null;
}

export interface ReportContentPayload {
  summary: string;
  strengths: string[];
  risks: string[];
  outlook: string;
  opinion: ReportOpinion;
  disclaimer: string;
}

export interface AnalysisReportResponse {
  stock_code: string;
  report_date: string;
  provider: string;
  model_id: string;
  content: ReportContentPayload;
  sources: ReportSourceItem[];
  cache_hit: boolean;
  token_in: number | null;
  token_out: number | null;
  elapsed_ms: number | null;
}

export const OPINION_LABELS: Record<ReportOpinion, string> = {
  BUY: '매수 우위',
  HOLD: '보유',
  SELL: '매도 우위',
  NEUTRAL: '중립',
};

export const OPINION_COLORS: Record<ReportOpinion, string> = {
  BUY: 'text-[#FF4D6A] bg-[#FF4D6A]/10 border-[#FF4D6A]/30',
  SELL: 'text-[#6395FF] bg-[#6395FF]/10 border-[#6395FF]/30',
  HOLD: 'text-[#FFCC00] bg-[#FFCC00]/10 border-[#FFCC00]/30',
  NEUTRAL: 'text-[#6B7A90] bg-white/5 border-white/10',
};

export const SOURCE_TYPE_LABELS: Record<ReportSourceType, string> = {
  dart: 'DART',
  krx: 'KRX',
  ecos: 'ECOS',
  news: '뉴스',
  official: '공식',
};

export const TIER_LABELS: Record<1 | 2, string> = {
  1: 'Tier 1 공식',
  2: 'Tier 2 정성',
};

'use client';

import Link from 'next/link';
import { use, useEffect, useState } from 'react';
import { generateReport } from '@/lib/api/reports';
import {
  AnalysisReportResponse,
  OPINION_COLORS,
  OPINION_LABELS,
  ReportSourceItem,
  SOURCE_TYPE_LABELS,
  TIER_LABELS,
} from '@/types/report';

export default function ReportPage({
  params,
}: {
  params: Promise<{ stockCode: string }>;
}) {
  const { stockCode } = use(params);
  const [report, setReport] = useState<AnalysisReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // refreshTick: 재생성 버튼 누를 때마다 증가 → useEffect 재실행 트리거.
  const [refreshTick, setRefreshTick] = useState(0);

  // render-phase state reset (React 공식 patterns: Storing information from previous renders).
  // React 19 의 react-hooks/set-state-in-effect 룰을 피하면서 즉시 시각 피드백을 준다.
  const currentKey = `${stockCode}:${refreshTick}`;
  const [prevKey, setPrevKey] = useState(currentKey);
  if (currentKey !== prevKey) {
    setPrevKey(currentKey);
    const force = refreshTick > 0;
    if (force) setRefreshing(true);
    else setLoading(true);
    setError(null);
  }

  useEffect(() => {
    // cancelled 플래그: stockCode 빠르게 바뀔 때 stale 응답이 최신 상태 덮어쓰는 race 방어.
    let cancelled = false;
    const force = refreshTick > 0;
    generateReport(stockCode, force)
      .then(r => {
        if (cancelled) return;
        setReport(r);
      })
      .catch(err => {
        if (cancelled) return;
        setError((err as Error).message);
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
        setRefreshing(false);
      });
    return () => {
      cancelled = true;
    };
  }, [stockCode, refreshTick]);

  function triggerRefresh() {
    setRefreshTick(t => t + 1);
  }

  return (
    <main className="max-w-4xl mx-auto px-4 sm:px-5 py-5 sm:py-7">
      <header className="mb-5">
        <div className="flex items-center gap-2 text-xs text-[#6B7A90] mb-2">
          <Link href="/portfolio" className="hover:text-[#E8ECF1]">
            포트폴리오
          </Link>
          <span aria-hidden="true">/</span>
          <Link href={`/stocks/${stockCode}`} className="hover:text-[#E8ECF1]">
            종목
          </Link>
          <span aria-hidden="true">/</span>
          <span>AI 리포트</span>
        </div>
        <div className="flex items-end justify-between gap-3 flex-wrap">
          <div>
            <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight">
              AI 분석 리포트
            </h1>
            <div className="text-sm text-[#6B7A90] mt-0.5">
              <span className="font-[family-name:var(--font-mono)]">{stockCode}</span>
              {report && (
                <>
                  <span className="mx-2" aria-hidden="true">
                    ·
                  </span>
                  <span>발행일 {report.report_date}</span>
                  {report.cache_hit && (
                    <span className="ml-2 text-[0.7rem] px-1.5 py-0.5 rounded bg-white/[0.04] border border-white/[0.06]">
                      캐시
                    </span>
                  )}
                </>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={triggerRefresh}
            disabled={loading || refreshing}
            className="px-4 py-2 rounded-lg text-[0.85rem] font-medium bg-[#6395FF] text-white hover:bg-[#7BA5FF] shadow-[0_2px_8px_rgba(99,149,255,0.3)] disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50"
          >
            {refreshing ? '재생성 중…' : '다시 생성'}
          </button>
        </div>
      </header>

      {loading && <ReportSkeleton />}

      {error && !loading && (
        <div className="bg-[#FF4D6A]/10 border border-[#FF4D6A]/30 rounded-[14px] p-6">
          <p className="text-[#FFB1BE] font-medium mb-1">리포트 생성 실패</p>
          <p className="text-sm text-[#FFB1BE]/80">{error}</p>
          <button
            type="button"
            onClick={triggerRefresh}
            className="mt-4 px-3 py-1.5 rounded-lg text-xs bg-white/[0.04] border border-white/[0.06] text-[#E8ECF1]"
          >
            다시 시도
          </button>
        </div>
      )}

      {!loading && !error && report && <ReportBody report={report} />}
    </main>
  );
}

function ReportBody({ report }: { report: AnalysisReportResponse }) {
  const c = report.content;
  return (
    <article className="space-y-5">
      {/* Opinion + summary */}
      <section
        aria-labelledby="opinion-title"
        className={`bg-[#131720]/85 backdrop-blur border rounded-[14px] p-5 ${
          OPINION_COLORS[c.opinion]
        }`}
      >
        <div className="flex items-center gap-3 flex-wrap mb-3">
          <h2
            id="opinion-title"
            className="font-[family-name:var(--font-display)] text-xl font-bold tracking-tight"
          >
            {OPINION_LABELS[c.opinion]}
          </h2>
          <span className="font-[family-name:var(--font-mono)] text-[0.65rem] uppercase tracking-wider opacity-60">
            {c.opinion}
          </span>
        </div>
        <p className="text-[#E8ECF1] leading-relaxed">{c.summary}</p>
      </section>

      {/* Strengths vs Risks */}
      <section
        aria-labelledby="points-title"
        className="grid grid-cols-1 md:grid-cols-2 gap-3"
      >
        <h2 id="points-title" className="sr-only">
          주요 강점과 리스크
        </h2>
        <PointsCard
          heading="강점"
          color="text-[#FF4D6A]"
          accent="border-[#FF4D6A]/30 bg-[#FF4D6A]/5"
          items={c.strengths}
        />
        <PointsCard
          heading="리스크"
          color="text-[#6395FF]"
          accent="border-[#6395FF]/30 bg-[#6395FF]/5"
          items={c.risks}
        />
      </section>

      {/* Outlook */}
      <section
        aria-labelledby="outlook-title"
        className="bg-[#131720]/85 backdrop-blur border border-white/[0.06] rounded-[14px] p-5"
      >
        <h2
          id="outlook-title"
          className="font-[family-name:var(--font-display)] text-sm text-[#6B7A90] uppercase tracking-wider mb-3"
        >
          전망
        </h2>
        <p className="text-[#E8ECF1] leading-relaxed whitespace-pre-wrap">{c.outlook}</p>
      </section>

      {/* Sources */}
      {report.sources.length > 0 && (
        <section
          aria-labelledby="sources-title"
          className="bg-[#131720]/85 backdrop-blur border border-white/[0.06] rounded-[14px] p-5"
        >
          <h2
            id="sources-title"
            className="font-[family-name:var(--font-display)] text-sm text-[#6B7A90] uppercase tracking-wider mb-3"
          >
            출처
          </h2>
          <ul role="list" className="space-y-2">
            {report.sources.map((s, idx) => (
              <li key={`${s.url}-${idx}`}>
                <SourceRow source={s} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Disclaimer + meta */}
      <footer className="text-xs text-[#7A8699] space-y-1">
        <p>{c.disclaimer}</p>
        <p className="font-[family-name:var(--font-mono)]">
          {report.provider} / {report.model_id}
          {report.elapsed_ms !== null && (
            <>
              {' · '}
              {report.elapsed_ms}ms
            </>
          )}
          {report.token_in !== null && report.token_out !== null && (
            <>
              {' · '}
              {report.token_in}↓ {report.token_out}↑ tokens
            </>
          )}
        </p>
      </footer>
    </article>
  );
}

function PointsCard({
  heading,
  color,
  accent,
  items,
}: {
  heading: string;
  color: string;
  accent: string;
  items: string[];
}) {
  return (
    <div className={`border rounded-[14px] p-5 ${accent}`}>
      <h3
        className={`font-[family-name:var(--font-display)] text-sm uppercase tracking-wider mb-3 ${color}`}
      >
        {heading}
      </h3>
      <ul role="list" className="space-y-2 text-sm leading-relaxed">
        {items.map((it, i) => (
          <li key={i} className="flex gap-2">
            <span className={`flex-shrink-0 ${color}`} aria-hidden="true">
              •
            </span>
            <span className="text-[#E8ECF1]">{it}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// 프론트 defense-in-depth: 백엔드가 URL 스킴을 검증하지만, 만약 필터가 우회되어
// javascript:/data:/file: 가 들어와도 브라우저에서 실행되지 않도록 href 를 무력화한다.
// rel="noopener noreferrer" 는 opener 접근만 막을 뿐 javascript: 실행은 막지 못한다.
function safeHref(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? url : '#';
  } catch {
    return '#';
  }
}

function SourceRow({ source }: { source: ReportSourceItem }) {
  const href = safeHref(source.url);
  const unsafe = href === '#';
  return (
    <a
      href={href}
      target={unsafe ? undefined : '_blank'}
      rel="noopener noreferrer"
      aria-label={`${source.label} (새 탭에서 열기)`}
      aria-disabled={unsafe || undefined}
      className="flex items-start gap-2 sm:items-center sm:gap-3 px-3 py-2 rounded-lg hover:bg-white/[0.03] transition-colors group"
    >
      <span
        className={`shrink-0 mt-0.5 sm:mt-0 px-1.5 py-0.5 rounded text-[0.6rem] font-bold font-[family-name:var(--font-mono)] ${
          source.tier === 1
            ? 'bg-[#FF4D6A]/10 text-[#FF4D6A] border border-[#FF4D6A]/30'
            : 'bg-[#FFCC00]/10 text-[#FFCC00] border border-[#FFCC00]/30'
        }`}
        title={TIER_LABELS[source.tier]}
      >
        T{source.tier}
      </span>
      {/* Mobile: 라벨 위 / 메타 아래 2줄. Desktop: 한 줄 flatten. */}
      <div className="min-w-0 flex-1 flex flex-col gap-0.5 sm:flex-row sm:items-center sm:gap-3">
        <span className="order-2 sm:order-none sm:flex-1 text-sm text-[#E8ECF1] group-hover:text-[#6395FF] transition-colors truncate">
          {source.label}
        </span>
        <div className="order-1 sm:order-none flex items-center gap-2 sm:contents">
          <span className="text-[0.65rem] text-[#6B7A90] uppercase tracking-wider font-medium sm:w-12 sm:order-first shrink-0">
            {SOURCE_TYPE_LABELS[source.type] ?? source.type}
          </span>
          {source.published_at && (
            <span className="text-[0.65rem] text-[#7A8699] font-[family-name:var(--font-mono)] shrink-0">
              {source.published_at}
            </span>
          )}
        </div>
      </div>
      <span
        className="shrink-0 text-[0.7rem] text-[#7A8699] group-hover:text-[#6395FF] transition-colors"
        aria-hidden="true"
      >
        ↗
      </span>
    </a>
  );
}

function ReportSkeleton() {
  return (
    <div className="space-y-5" aria-busy="true" aria-live="polite">
      <div className="h-28 bg-[#131720] rounded-[14px] animate-pulse" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="h-40 bg-[#131720] rounded-[14px] animate-pulse" />
        <div className="h-40 bg-[#131720] rounded-[14px] animate-pulse" />
      </div>
      <div className="h-32 bg-[#131720] rounded-[14px] animate-pulse" />
      <div className="h-24 bg-[#131720] rounded-[14px] animate-pulse" />
    </div>
  );
}

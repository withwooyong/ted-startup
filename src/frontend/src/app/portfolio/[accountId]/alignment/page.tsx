'use client';

import Link from 'next/link';
import { use, useEffect, useState } from 'react';
import { getSignalAlignment } from '@/lib/api/portfolio';
import type { SignalAlignmentReport } from '@/types/portfolio';

const SIGNAL_TYPE_LABELS: Record<string, string> = {
  RAPID_DECLINE: '대차잔고 급감',
  TREND_REVERSAL: '추세전환',
  SHORT_SQUEEZE: '숏스퀴즈',
};

const GRADE_COLORS: Record<string, string> = {
  A: 'text-[#FF4D6A] bg-[#FF4D6A]/10',
  B: 'text-[#FF8B3E] bg-[#FF8B3E]/10',
  C: 'text-[#FFCC00] bg-[#FFCC00]/10',
  D: 'text-[#4A5568] bg-white/5',
};

export default function AlignmentPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId: raw } = use(params);
  const parsedAccountId = Number(raw);
  const isValidAccount = Number.isInteger(parsedAccountId) && parsedAccountId > 0;
  const [report, setReport] = useState<SignalAlignmentReport | null>(null);
  const [minScore, setMinScore] = useState(60);
  const [loading, setLoading] = useState(isValidAccount);
  const [error, setError] = useState<string | null>(
    isValidAccount ? null : '유효하지 않은 계좌 ID 입니다',
  );

  // render-phase state reset — 의존성 변경 시 즉시 로딩 상태 진입.
  const currentKey = `${parsedAccountId}:${minScore}`;
  const [prevKey, setPrevKey] = useState(currentKey);
  if (isValidAccount && currentKey !== prevKey) {
    setPrevKey(currentKey);
    setLoading(true);
    setError(null);
  }

  useEffect(() => {
    if (!isValidAccount) return;
    let cancelled = false;
    getSignalAlignment(parsedAccountId, { min_score: minScore })
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
      });
    return () => {
      cancelled = true;
    };
  }, [parsedAccountId, minScore, isValidAccount]);

  const accountId = parsedAccountId;

  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-5 py-5 sm:py-7">
      <header className="mb-5">
        <Link
          href="/portfolio"
          className="inline-flex items-center gap-1 text-xs text-[#6B7A90] hover:text-[#E8ECF1] mb-2"
        >
          ← 포트폴리오
        </Link>
        <h1 className="font-[family-name:var(--font-display)] text-xl font-bold">
          시그널 정합도 (계좌 #{accountId})
        </h1>
        <p className="text-xs text-[#6B7A90] mt-1">
          보유 종목에 대해 탐지된 시그널 — 최근 30일 · 스코어 {minScore}점 이상
        </p>
      </header>

      <div className="flex items-center gap-3 mb-5 text-sm">
        <label className="text-[#6B7A90]" htmlFor="min-score">
          최소 스코어
        </label>
        <input
          id="min-score"
          type="range"
          min={0}
          max={100}
          step={5}
          value={minScore}
          onChange={e => setMinScore(Number(e.target.value))}
          className="w-40"
        />
        <span className="font-[family-name:var(--font-mono)] text-xs w-8 text-right">
          {minScore}
        </span>
      </div>

      {loading && (
        <div className="grid grid-cols-1 gap-3" aria-busy="true">
          {[1, 2, 3].map(i => (
            <div
              key={i}
              className="h-24 bg-[#131720] rounded-[14px] animate-pulse"
            />
          ))}
        </div>
      )}

      {error && (
        <div className="bg-[#FF4D6A]/10 border border-[#FF4D6A]/30 text-[#FFB1BE] px-4 py-3 rounded-[10px] text-sm">
          {error}
        </div>
      )}

      {!loading && !error && report && (
        <>
          <div className="flex gap-3 text-xs text-[#6B7A90] mb-4">
            <span>
              전체 보유{' '}
              <b className="text-[#E8ECF1] font-[family-name:var(--font-mono)]">
                {report.total_holdings}
              </b>
            </span>
            <span aria-hidden="true">·</span>
            <span>
              시그널 매칭{' '}
              <b className="text-[#6395FF] font-[family-name:var(--font-mono)]">
                {report.aligned_holdings}
              </b>
            </span>
          </div>

          {report.items.length === 0 ? (
            <div className="bg-[#131720]/85 border border-white/[0.06] rounded-[14px] p-8 text-center">
              <p className="text-[#6B7A90] text-sm">
                기간 내 해당 기준(스코어 ≥ {minScore}) 의 시그널이 없습니다.
              </p>
            </div>
          ) : (
            <ul role="list" className="grid grid-cols-1 gap-3">
              {report.items.map(item => (
                <li
                  key={item.stock_id}
                  className="bg-[#131720]/85 backdrop-blur border border-white/[0.06] rounded-[14px] p-4 hover:border-[#6395FF]/30 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <Link
                          href={`/stocks/${item.stock_code}`}
                          className="font-[family-name:var(--font-display)] text-base font-semibold hover:text-[#6395FF] transition-colors"
                        >
                          {item.stock_name}
                        </Link>
                        <span className="text-[0.7rem] text-[#7A8699] font-[family-name:var(--font-mono)]">
                          {item.stock_code}
                        </span>
                      </div>
                      <div className="text-xs text-[#6B7A90] mt-1">
                        보유{' '}
                        <span className="font-[family-name:var(--font-mono)]">
                          {item.quantity.toLocaleString('ko-KR')}
                        </span>
                        주 · 평단{' '}
                        <span className="font-[family-name:var(--font-mono)]">
                          {Number(item.avg_buy_price).toLocaleString('ko-KR')}
                        </span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-[0.7rem] text-[#7A8699] uppercase tracking-wider">
                        Max Score
                      </div>
                      <div className="font-[family-name:var(--font-display)] text-2xl font-bold">
                        {item.max_score}
                      </div>
                      <div className="text-[0.65rem] text-[#6B7A90] mt-0.5">
                        총 {item.hit_count}회
                      </div>
                    </div>
                  </div>

                  <ul className="mt-3 flex flex-wrap gap-2" role="list">
                    {item.signals.slice(0, 6).map((s, idx) => (
                      <li
                        key={`${s.signal_date}-${s.signal_type}-${idx}`}
                        className={`items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/[0.03] border border-white/[0.04] text-[0.7rem] ${
                          idx >= 3 ? 'hidden sm:flex' : 'flex'
                        }`}
                      >
                        <span
                          className={`px-1.5 py-0.5 rounded text-[0.65rem] font-bold ${
                            GRADE_COLORS[s.grade] ?? GRADE_COLORS.D
                          }`}
                        >
                          {s.grade}
                        </span>
                        <span>
                          {SIGNAL_TYPE_LABELS[s.signal_type] ?? s.signal_type}
                        </span>
                        <span className="text-[#7A8699] font-[family-name:var(--font-mono)]">
                          {s.signal_date}
                        </span>
                        <span className="font-[family-name:var(--font-mono)] text-[#6B7A90]">
                          {s.score}
                        </span>
                      </li>
                    ))}
                    {/* 모바일에서 3개 초과분은 "+N" 배지로 압축 (최대 6개까지 집계) */}
                    {item.signals.length > 3 && (
                      <li
                        aria-label={`숨겨진 시그널 ${Math.min(item.signals.length, 6) - 3}개`}
                        className="sm:hidden flex items-center px-2.5 py-1 rounded-md bg-white/[0.03] border border-white/[0.04] text-[0.7rem] text-[#6B7A90] font-[family-name:var(--font-mono)]"
                      >
                        +{Math.min(item.signals.length, 6) - 3}개
                      </li>
                    )}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </main>
  );
}

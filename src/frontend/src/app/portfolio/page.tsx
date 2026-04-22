'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import {
  createSnapshot,
  getPerformance,
  listAccounts,
  listHoldings,
  syncFromKis,
} from '@/lib/api/portfolio';
import type {
  Account,
  Holding,
  PerformanceReport,
} from '@/types/portfolio';
import { ExcelImportPanel } from '@/components/features/ExcelImportPanel';

function formatNumber(value: string | number | null, opts?: { fraction?: number }): string {
  if (value === null || value === undefined || value === '') return '-';
  const n = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(n)) return '-';
  return n.toLocaleString('ko-KR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: opts?.fraction ?? 0,
  });
}

function formatPct(value: string | null): string {
  if (value === null) return '-';
  const n = Number(value);
  if (Number.isNaN(n)) return '-';
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

function pnlColor(pnl: number): string {
  if (pnl > 0) return 'text-[#FF4D6A]';
  if (pnl < 0) return 'text-[#6395FF]';
  return 'text-[#6B7A90]';
}

export default function PortfolioPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selected, setSelected] = useState<Account | null>(null);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [performance, setPerformance] = useState<PerformanceReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionPending, setActionPending] = useState<string | null>(null);
  const [banner, setBanner] = useState<{ kind: 'info' | 'error'; text: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    listAccounts()
      .then(rows => {
        if (cancelled) return;
        setAccounts(rows);
        setSelected(rows[0] ?? null);
        setLoading(false);
      })
      .catch(err => {
        if (cancelled) return;
        setBanner({ kind: 'error', text: `계좌 조회 실패: ${err.message}` });
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selected) {
      setHoldings([]);
      setPerformance(null);
      return;
    }
    let cancelled = false;
    Promise.all([listHoldings(selected.id), getPerformance(selected.id)])
      .then(([h, p]) => {
        if (cancelled) return;
        setHoldings(h);
        setPerformance(p);
      })
      .catch(err => {
        if (cancelled) return;
        setBanner({ kind: 'error', text: `보유·성과 조회 실패: ${err.message}` });
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  async function refreshCurrent(): Promise<void> {
    if (!selected) return;
    // 실패는 상위 핸들러에서 배너로 표시하도록 전파. 침묵 실패로 성공 배너와
    // 실제 stale 데이터가 불일치하는 UX 문제를 차단.
    const [h, p] = await Promise.all([
      listHoldings(selected.id),
      getPerformance(selected.id),
    ]);
    setHoldings(h);
    setPerformance(p);
  }

  async function handleSnapshot() {
    if (!selected) return;
    setActionPending('snapshot');
    setBanner(null);
    try {
      const snap = await createSnapshot(selected.id);
      setBanner({
        kind: 'info',
        text: `스냅샷 저장 완료: 평가금액 ${formatNumber(snap.total_value)}원 · 미실현 ${formatNumber(snap.unrealized_pnl)}원`,
      });
      try {
        await refreshCurrent();
      } catch (refreshErr) {
        // 액션 자체는 성공했으나 재조회 실패 — 정확한 상태를 사용자에게 알림.
        setBanner({
          kind: 'error',
          text: `스냅샷 저장 완료했지만 데이터 재조회 실패: ${(refreshErr as Error).message}`,
        });
      }
    } catch (err) {
      setBanner({ kind: 'error', text: `스냅샷 실패: ${(err as Error).message}` });
    } finally {
      setActionPending(null);
    }
  }

  async function handleSync() {
    if (!selected) return;
    setActionPending('sync');
    setBanner(null);
    try {
      const result = await syncFromKis(selected.id);
      const successMsg = `KIS 동기화 완료: 신규 ${result.created_count} · 갱신 ${result.updated_count} · 그대로 ${result.unchanged_count}`;
      try {
        await refreshCurrent();
        setBanner({ kind: 'info', text: successMsg });
      } catch (refreshErr) {
        setBanner({
          kind: 'error',
          text: `${successMsg} — 단, 재조회 실패: ${(refreshErr as Error).message}`,
        });
      }
    } catch (err) {
      // 실계좌 sync 에서 404 는 "credential 미등록" 이 유일한 원인 (계좌는 selected 에서
      // 이미 유효함을 보장). 사용자에게 "설정에서 자격증명 등록" 맥락 메시지 표시.
      const status =
        err && typeof err === 'object' && 'status' in err
          ? (err as { status?: number }).status
          : undefined;
      if (status === 404 && selected?.connection_type === 'kis_rest_real') {
        setBanner({
          kind: 'error',
          text: 'KIS 자격증명이 등록되지 않았습니다. 설정 페이지에서 등록 후 재시도해주세요.',
        });
      } else {
        setBanner({ kind: 'error', text: `KIS 동기화 실패: ${(err as Error).message}` });
      }
    } finally {
      setActionPending(null);
    }
  }

  const totalValue = holdings.reduce(
    (acc, h) => acc + Number(h.avg_buy_price) * h.quantity,
    0,
  );

  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-5 py-5 sm:py-7">
      <header className="mb-5 sm:mb-7">
        <span
          className="font-[family-name:var(--font-display)] text-sm text-[#6B7A90]"
          aria-hidden="true"
        >
          내 포트폴리오
        </span>
        <h1 className="sr-only">포트폴리오 대시보드</h1>
      </header>

      {banner && (
        <div
          role={banner.kind === 'error' ? 'alert' : 'status'}
          className={`mb-4 px-4 py-3 rounded-[10px] text-sm border ${
            banner.kind === 'error'
              ? 'bg-[#FF4D6A]/10 border-[#FF4D6A]/30 text-[#FFB1BE]'
              : 'bg-[#6395FF]/10 border-[#6395FF]/30 text-[#B0CAFF]'
          }`}
        >
          {banner.text}
        </div>
      )}

      {/* Account switcher */}
      <section aria-labelledby="account-title" className="mb-5">
        <h2 id="account-title" className="sr-only">
          계좌 선택
        </h2>
        {loading ? (
          <div className="h-12 bg-[#131720] rounded-[12px] animate-pulse" aria-busy="true" />
        ) : accounts.length === 0 ? (
          <div className="bg-[#131720]/85 backdrop-blur border border-white/[0.06] rounded-[14px] p-6 text-center">
            <p className="text-[#6B7A90] text-sm">등록된 계좌가 없습니다.</p>
            <p className="text-[#3D4A5C] text-xs mt-1">
              관리자 API 로 <code>POST /api/portfolio/accounts</code> 호출 후 새로고침하세요.
            </p>
          </div>
        ) : (
          <div
            role="tablist"
            aria-label="계좌 탭"
            className="flex gap-1 bg-[#131720] rounded-[10px] p-0.5 border border-white/[0.06] overflow-x-auto"
          >
            {accounts.map(a => {
              const active = selected?.id === a.id;
              return (
                <button
                  key={a.id}
                  role="tab"
                  aria-selected={active}
                  onClick={() => setSelected(a)}
                  className={`px-4 py-2 rounded-lg text-[0.85rem] font-medium whitespace-nowrap transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50 ${
                    active
                      ? 'text-white bg-[#6395FF] shadow-[0_2px_8px_rgba(99,149,255,0.3)]'
                      : 'text-[#6B7A90] hover:text-[#E8ECF1]'
                  }`}
                >
                  {a.account_alias}
                  <span className="text-[0.65rem] opacity-60 ml-2 font-[family-name:var(--font-mono)]">
                    {a.broker_code}·{a.connection_type}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </section>

      {selected && (
        <>
          {/* Metric Cards */}
          <section
            aria-labelledby="metrics-title"
            className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5 sm:mb-7"
          >
            <h2 id="metrics-title" className="sr-only">
              계좌 지표
            </h2>
            <Metric label="보유 종목 수" value={String(holdings.length)} mono />
            <Metric
              label="매입 원가 합계"
              value={formatNumber(totalValue)}
              unit="원"
              mono
            />
            <Metric
              label="누적 수익률 (3M)"
              value={formatPct(performance?.total_return_pct ?? null)}
              colorClass={pnlColor(Number(performance?.total_return_pct ?? 0))}
            />
            <Metric
              label="MDD (3M)"
              value={formatPct(performance?.max_drawdown_pct ?? null)}
              colorClass="text-[#6395FF]"
            />
          </section>

          {/* Action bar */}
          <section className="flex flex-wrap gap-2 mb-4">
            <ActionButton
              onClick={handleSnapshot}
              disabled={actionPending !== null}
              pending={actionPending === 'snapshot'}
            >
              스냅샷 생성
            </ActionButton>
            {(selected.connection_type === 'kis_rest_mock' ||
              selected.connection_type === 'kis_rest_real') && (
              <ActionButton
                onClick={handleSync}
                disabled={actionPending !== null}
                pending={actionPending === 'sync'}
                variant="accent"
              >
                {selected.connection_type === 'kis_rest_real'
                  ? 'KIS 실계좌 동기화'
                  : 'KIS 모의 동기화'}
              </ActionButton>
            )}
            <Link
              href={`/portfolio/${selected.id}/alignment`}
              className="px-4 py-2 rounded-lg text-[0.85rem] font-medium bg-white/[0.04] border border-white/[0.06] text-[#E8ECF1] hover:bg-white/[0.08] transition-colors"
            >
              시그널 정합도
            </Link>
          </section>

          {/* 거래내역 엑셀 import (P10 온보딩 1단계) — 실 계좌 연결 없이도 사용 가능 */}
          <ExcelImportPanel
            accountId={selected.id}
            onSuccess={() => {
              refreshCurrent().catch((refreshErr: unknown) => {
                // refreshCurrent 가 throw 하면 여기서 잡아 배너로 알림.
                const msg = refreshErr instanceof Error ? refreshErr.message : String(refreshErr);
                setBanner({
                  kind: 'error',
                  text: `가져오기 성공했으나 재조회 실패: ${msg}`,
                });
              });
            }}
          />

          {/* Holdings table */}
          <section aria-labelledby="holdings-title">
            <h2
              id="holdings-title"
              className="font-[family-name:var(--font-display)] text-sm text-[#6B7A90] mb-2"
            >
              보유 종목
            </h2>
            {holdings.length === 0 ? (
              <div className="bg-[#131720]/85 border border-white/[0.06] rounded-[14px] p-8 text-center">
                <p className="text-[#6B7A90] text-sm">보유 종목이 없습니다.</p>
              </div>
            ) : (
              <>
                {/* Desktop / tablet: table (>= sm) */}
                <div className="hidden sm:block bg-[#131720]/85 backdrop-blur border border-white/[0.06] rounded-[14px] overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-white/[0.02]">
                      <tr className="text-left text-[0.7rem] text-[#3D4A5C] uppercase tracking-wider">
                        <th className="px-4 py-2.5 font-[family-name:var(--font-display)] font-medium">
                          종목
                        </th>
                        <th className="px-4 py-2.5 text-right font-[family-name:var(--font-display)] font-medium">
                          수량
                        </th>
                        <th className="px-4 py-2.5 text-right font-[family-name:var(--font-display)] font-medium">
                          평단가
                        </th>
                        <th className="px-4 py-2.5 text-right font-[family-name:var(--font-display)] font-medium">
                          매입원가
                        </th>
                        <th className="px-4 py-2.5 text-right font-[family-name:var(--font-display)] font-medium">
                          리포트
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {holdings.map(h => {
                        const cost = Number(h.avg_buy_price) * h.quantity;
                        return (
                          <tr
                            key={h.stock_id}
                            data-testid="holding-row"
                            className="border-t border-white/[0.04] hover:bg-white/[0.02]"
                          >
                            <td className="px-4 py-3">
                              <Link
                                href={`/stocks/${h.stock_code ?? ''}`}
                                className="font-medium hover:text-[#6395FF] transition-colors"
                              >
                                {h.stock_name ?? '(이름 없음)'}
                              </Link>
                              <span className="ml-2 text-[0.7rem] text-[#3D4A5C] font-[family-name:var(--font-mono)]">
                                {h.stock_code ?? ''}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-right font-[family-name:var(--font-mono)] tabular-nums">
                              {formatNumber(h.quantity)}
                            </td>
                            <td className="px-4 py-3 text-right font-[family-name:var(--font-mono)] tabular-nums text-[#6B7A90]">
                              {formatNumber(h.avg_buy_price, { fraction: 2 })}
                            </td>
                            <td className="px-4 py-3 text-right font-[family-name:var(--font-mono)] tabular-nums">
                              {formatNumber(cost)}
                            </td>
                            <td className="px-4 py-3 text-right">
                              {h.stock_code && (
                                <Link
                                  href={`/reports/${h.stock_code}`}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[0.7rem] bg-[#6395FF]/10 text-[#6395FF] border border-[#6395FF]/30 hover:bg-[#6395FF]/20 transition-colors"
                                >
                                  AI 리포트 →
                                </Link>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Mobile: card list (< sm) */}
                <ul className="sm:hidden space-y-3">
                  {holdings.map(h => {
                    const cost = Number(h.avg_buy_price) * h.quantity;
                    return (
                      <li
                        key={h.stock_id}
                        data-testid="holding-row"
                        className="bg-[#131720]/85 backdrop-blur border border-white/[0.06] rounded-[14px] p-4"
                      >
                        <div className="flex items-start justify-between gap-3 mb-3">
                          <div className="min-w-0 flex-1">
                            <Link
                              href={`/stocks/${h.stock_code ?? ''}`}
                              className="block font-medium text-[#E8ECF1] hover:text-[#6395FF] transition-colors truncate"
                            >
                              {h.stock_name ?? '(이름 없음)'}
                            </Link>
                            <span className="text-[0.7rem] text-[#3D4A5C] font-[family-name:var(--font-mono)]">
                              {h.stock_code ?? ''}
                            </span>
                          </div>
                          {h.stock_code && (
                            <Link
                              href={`/reports/${h.stock_code}`}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[0.7rem] bg-[#6395FF]/10 text-[#6395FF] border border-[#6395FF]/30 hover:bg-[#6395FF]/20 transition-colors shrink-0 whitespace-nowrap"
                            >
                              AI 리포트 →
                            </Link>
                          )}
                        </div>
                        <dl className="grid grid-cols-3 gap-2 text-[0.75rem]">
                          <div>
                            <dt className="text-[0.65rem] text-[#3D4A5C] uppercase tracking-wider font-[family-name:var(--font-display)] font-medium mb-0.5">
                              수량
                            </dt>
                            <dd className="font-[family-name:var(--font-mono)] tabular-nums text-[#E8ECF1]">
                              {formatNumber(h.quantity)}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-[0.65rem] text-[#3D4A5C] uppercase tracking-wider font-[family-name:var(--font-display)] font-medium mb-0.5">
                              평단가
                            </dt>
                            <dd className="font-[family-name:var(--font-mono)] tabular-nums text-[#6B7A90]">
                              {formatNumber(h.avg_buy_price, { fraction: 2 })}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-[0.65rem] text-[#3D4A5C] uppercase tracking-wider font-[family-name:var(--font-display)] font-medium mb-0.5">
                              매입원가
                            </dt>
                            <dd className="font-[family-name:var(--font-mono)] tabular-nums text-[#E8ECF1]">
                              {formatNumber(cost)}
                            </dd>
                          </div>
                        </dl>
                      </li>
                    );
                  })}
                </ul>
              </>
            )}
          </section>
        </>
      )}
    </main>
  );
}

function Metric({
  label,
  value,
  unit,
  mono,
  colorClass,
}: {
  label: string;
  value: string;
  unit?: string;
  mono?: boolean;
  colorClass?: string;
}) {
  return (
    <div className="bg-[#131720]/85 backdrop-blur border border-white/[0.06] rounded-[14px] p-4">
      <div className="text-[0.7rem] text-[#3D4A5C] uppercase tracking-wider font-[family-name:var(--font-display)] font-medium mb-2">
        {label}
      </div>
      <div
        className={`font-[family-name:var(--font-display)] text-2xl sm:text-3xl font-bold tracking-tight ${
          mono ? 'font-[family-name:var(--font-mono)] tabular-nums' : ''
        } ${colorClass ?? ''}`}
      >
        {value}
        {unit && <span className="text-base font-normal text-[#6B7A90] ml-1">{unit}</span>}
      </div>
    </div>
  );
}

function ActionButton({
  children,
  onClick,
  disabled,
  pending,
  variant = 'default',
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  pending?: boolean;
  variant?: 'default' | 'accent';
}) {
  const base = 'px-4 py-2 rounded-lg text-[0.85rem] font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50';
  const style =
    variant === 'accent'
      ? 'bg-[#6395FF] text-white hover:bg-[#7BA5FF] shadow-[0_2px_8px_rgba(99,149,255,0.3)]'
      : 'bg-white/[0.04] border border-white/[0.06] text-[#E8ECF1] hover:bg-white/[0.08]';
  return (
    <button type="button" onClick={onClick} disabled={disabled} className={`${base} ${style}`}>
      {pending ? '처리 중…' : children}
    </button>
  );
}

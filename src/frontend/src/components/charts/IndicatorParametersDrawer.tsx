'use client';

import { useEffect, useId, useMemo, useRef, useState } from 'react';
import type { FormEvent, KeyboardEvent as ReactKeyboardEvent } from 'react';

import {
  DEFAULT_PARAMS,
  type IndicatorParams,
  type IndicatorPrefs,
  type MaWindows,
} from '@/lib/hooks/useIndicatorPreferences';

// v1.2 Cp 2β — 지표 파라미터 편집 Drawer.
//
// 역할: `useIndicatorPreferences` 의 params 를 사용자가 직접 편집.
// open 전환(close→open) 시 draft 를 현재 prefs 기준으로 리셋 → 취소 시 원상복귀.
// 검증 규칙은 `isValidPrefsV2` 와 동치이어야 한다 (저장 경로에서 이중검증 보장).
//
// 접근성: role="dialog" + aria-modal + ESC close + focus trap (Tab 순환).
// 포커스 진입은 첫 focusable 로, 이탈 시 호출자가 복원.

interface Props {
  open: boolean;
  prefs: IndicatorPrefs;
  onClose: () => void;
  onSave: (params: IndicatorParams) => void;
}

type Errors = {
  ma: Array<string | null>;
  rsi: { period: string | null; overbought: string | null; oversold: string | null };
  macd: { fast: string | null; slow: string | null; signal: string | null };
  bb: { period: string | null; k: string | null };
};

function emptyErrors(): Errors {
  return {
    ma: [null, null, null, null],
    rsi: { period: null, overbought: null, oversold: null },
    macd: { fast: null, slow: null, signal: null },
    bb: { period: null, k: null },
  };
}

function cloneParams(p: IndicatorParams): IndicatorParams {
  return {
    ma: [p.ma[0], p.ma[1], p.ma[2], p.ma[3]] as unknown as MaWindows,
    rsi: { ...p.rsi },
    macd: { ...p.macd },
    bb: { ...p.bb },
  };
}

function isInt(n: number): boolean {
  return Number.isInteger(n);
}

function validate(params: IndicatorParams): { errors: Errors; valid: boolean } {
  const errors = emptyErrors();
  let valid = true;

  params.ma.forEach((w, i) => {
    if (!isInt(w) || w < 2) {
      errors.ma[i] = '2 이상의 정수';
      valid = false;
    }
  });

  const { period: rp, overbought, oversold } = params.rsi;
  if (!isInt(rp) || rp < 2) {
    errors.rsi.period = '2 이상의 정수';
    valid = false;
  }
  if (!isInt(overbought) || overbought < 1 || overbought > 100) {
    errors.rsi.overbought = '1-100 정수';
    valid = false;
  }
  if (!isInt(oversold) || oversold < 1 || oversold > 100) {
    errors.rsi.oversold = '1-100 정수';
    valid = false;
  }
  if (
    errors.rsi.overbought == null &&
    errors.rsi.oversold == null &&
    overbought <= oversold
  ) {
    errors.rsi.overbought = '과매수 > 과매도 필요';
    valid = false;
  }

  const { fast, slow, signal } = params.macd;
  if (!isInt(fast) || fast < 2) {
    errors.macd.fast = '2 이상의 정수';
    valid = false;
  }
  if (!isInt(slow) || slow < 2) {
    errors.macd.slow = '2 이상의 정수';
    valid = false;
  }
  if (!isInt(signal) || signal < 2) {
    errors.macd.signal = '2 이상의 정수';
    valid = false;
  }
  if (
    errors.macd.fast == null &&
    errors.macd.slow == null &&
    fast >= slow
  ) {
    errors.macd.slow = 'fast < slow 필요';
    valid = false;
  }

  const { period: bp, k } = params.bb;
  if (!isInt(bp) || bp < 2) {
    errors.bb.period = '2 이상의 정수';
    valid = false;
  }
  if (!Number.isFinite(k) || k <= 0) {
    errors.bb.k = '양수';
    valid = false;
  }

  return { errors, valid };
}

export default function IndicatorParametersDrawer({
  open,
  prefs,
  onClose,
  onSave,
}: Props) {
  const titleId = useId();
  const [draft, setDraft] = useState<IndicatorParams>(() =>
    cloneParams(prefs.params),
  );
  const containerRef = useRef<HTMLDivElement | null>(null);
  const prevOpenRef = useRef(open);

  // close→open 전환 시 draft 를 현재 prefs 로 리셋. 렌더 중 set — 다음 렌더에 반영.
  if (prevOpenRef.current !== open) {
    prevOpenRef.current = open;
    if (open) setDraft(cloneParams(prefs.params));
  }

  const { errors, valid } = useMemo(() => validate(draft), [draft]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    const el = containerRef.current;
    if (!el) return;
    const first = el.querySelector<HTMLElement>(
      'input:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    first?.focus();
  }, [open]);

  function onKeyDownTrap(e: ReactKeyboardEvent<HTMLDivElement>) {
    if (e.key !== 'Tab') return;
    const el = containerRef.current;
    if (!el) return;
    const focusables = Array.from(
      el.querySelectorAll<HTMLElement>(
        'input:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    );
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement;
    if (e.shiftKey && active === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
  }

  if (!open) return null;

  function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    onSave(cloneParams(draft));
    onClose();
  }

  function handleReset() {
    setDraft(cloneParams(DEFAULT_PARAMS));
  }

  const setMa = (i: 0 | 1 | 2 | 3, v: number) =>
    setDraft(d => {
      const ma: MaWindows = [d.ma[0], d.ma[1], d.ma[2], d.ma[3]] as unknown as MaWindows;
      (ma as unknown as number[])[i] = v;
      return { ...d, ma };
    });

  const inputCls =
    'w-full rounded-lg bg-[#0B0E11] border border-white/[0.08] px-3 py-1.5 text-sm text-[#E8ECF1] tabular-nums focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50';
  const errorCls = 'text-[11px] text-[#FF6B6B] mt-1';
  const labelCls = 'block text-xs text-[#7A8699] mb-1';
  const sectionCls =
    'py-3 border-b border-white/[0.06] [&_summary]:cursor-pointer [&_summary]:select-none';
  const summaryCls = 'text-sm font-semibold text-[#E8ECF1] mb-3';

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center sm:justify-center"
      role="presentation"
    >
      <button
        type="button"
        aria-label="닫기"
        onClick={onClose}
        className="absolute inset-0 bg-black/60 cursor-default focus:outline-none"
        tabIndex={-1}
      />
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={onKeyDownTrap}
        className="relative w-full sm:max-w-md bg-[#131720] border border-white/[0.06] rounded-t-[14px] sm:rounded-[14px] p-5 max-h-[90dvh] overflow-y-auto"
      >
        <h2
          id={titleId}
          className="text-base font-bold text-[#E8ECF1] mb-4 font-[family-name:var(--font-display)]"
        >
          지표 파라미터 설정
        </h2>

        <form onSubmit={handleSave} noValidate>
          {/* MA — 4 슬롯 */}
          <details open className={sectionCls}>
            <summary className={summaryCls}>이동평균 (MA)</summary>
            <div className="grid grid-cols-2 gap-3">
              {([0, 1, 2, 3] as const).map(i => {
                const id = `${titleId}-ma-${i}`;
                const err = errors.ma[i];
                return (
                  <div key={i}>
                    <label htmlFor={id} className={labelCls}>{`MA #${i + 1} 기간`}</label>
                    <input
                      id={id}
                      type="number"
                      min={2}
                      step={1}
                      value={Number.isFinite(draft.ma[i]) ? String(draft.ma[i]) : ''}
                      onChange={e => setMa(i, Number(e.target.value))}
                      aria-invalid={err != null}
                      aria-describedby={err ? `${id}-error` : undefined}
                      className={inputCls}
                    />
                    {err && (
                      <p id={`${id}-error`} className={errorCls} role="alert">
                        {err}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </details>

          {/* RSI */}
          <details open className={sectionCls}>
            <summary className={summaryCls}>RSI</summary>
            <div className="grid grid-cols-3 gap-3">
              {(['period', 'overbought', 'oversold'] as const).map(f => {
                const id = `${titleId}-rsi-${f}`;
                const label = { period: '기간', overbought: '과매수', oversold: '과매도' }[f];
                const err = errors.rsi[f];
                return (
                  <div key={f}>
                    <label htmlFor={id} className={labelCls}>{label}</label>
                    <input
                      id={id}
                      type="number"
                      min={f === 'period' ? 2 : 1}
                      step={1}
                      value={Number.isFinite(draft.rsi[f]) ? String(draft.rsi[f]) : ''}
                      onChange={e =>
                        setDraft(d => ({
                          ...d,
                          rsi: { ...d.rsi, [f]: Number(e.target.value) },
                        }))
                      }
                      aria-invalid={err != null}
                      aria-describedby={err ? `${id}-error` : undefined}
                      className={inputCls}
                    />
                    {err && (
                      <p id={`${id}-error`} className={errorCls} role="alert">
                        {err}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </details>

          {/* MACD */}
          <details open className={sectionCls}>
            <summary className={summaryCls}>MACD</summary>
            <div className="grid grid-cols-3 gap-3">
              {(['fast', 'slow', 'signal'] as const).map(f => {
                const id = `${titleId}-macd-${f}`;
                const label = { fast: 'Fast', slow: 'Slow', signal: 'Signal' }[f];
                const err = errors.macd[f];
                return (
                  <div key={f}>
                    <label htmlFor={id} className={labelCls}>{label}</label>
                    <input
                      id={id}
                      type="number"
                      min={2}
                      step={1}
                      value={Number.isFinite(draft.macd[f]) ? String(draft.macd[f]) : ''}
                      onChange={e =>
                        setDraft(d => ({
                          ...d,
                          macd: { ...d.macd, [f]: Number(e.target.value) },
                        }))
                      }
                      aria-invalid={err != null}
                      aria-describedby={err ? `${id}-error` : undefined}
                      className={inputCls}
                    />
                    {err && (
                      <p id={`${id}-error`} className={errorCls} role="alert">
                        {err}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </details>

          {/* Bollinger Bands */}
          <details open className={sectionCls}>
            <summary className={summaryCls}>Bollinger Bands</summary>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor={`${titleId}-bb-period`} className={labelCls}>기간</label>
                <input
                  id={`${titleId}-bb-period`}
                  type="number"
                  min={2}
                  step={1}
                  value={Number.isFinite(draft.bb.period) ? String(draft.bb.period) : ''}
                  onChange={e =>
                    setDraft(d => ({
                      ...d,
                      bb: { ...d.bb, period: Number(e.target.value) },
                    }))
                  }
                  aria-invalid={errors.bb.period != null}
                  aria-describedby={errors.bb.period ? `${titleId}-bb-period-error` : undefined}
                  className={inputCls}
                />
                {errors.bb.period && (
                  <p id={`${titleId}-bb-period-error`} className={errorCls} role="alert">
                    {errors.bb.period}
                  </p>
                )}
              </div>
              <div>
                <label htmlFor={`${titleId}-bb-k`} className={labelCls}>k (표준편차 배수)</label>
                <input
                  id={`${titleId}-bb-k`}
                  type="number"
                  min={0.1}
                  step={0.1}
                  value={Number.isFinite(draft.bb.k) ? String(draft.bb.k) : ''}
                  onChange={e =>
                    setDraft(d => ({
                      ...d,
                      bb: { ...d.bb, k: Number(e.target.value) },
                    }))
                  }
                  aria-invalid={errors.bb.k != null}
                  aria-describedby={errors.bb.k ? `${titleId}-bb-k-error` : undefined}
                  className={inputCls}
                />
                {errors.bb.k && (
                  <p id={`${titleId}-bb-k-error`} className={errorCls} role="alert">
                    {errors.bb.k}
                  </p>
                )}
              </div>
            </div>
          </details>

          <div className="flex justify-between gap-2 pt-4">
            <button
              type="button"
              onClick={handleReset}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-[#7A8699] hover:text-[#E8ECF1] border border-white/[0.08] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50"
            >
              기본값 복원
            </button>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-[#7A8699] hover:text-[#E8ECF1] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50"
              >
                취소
              </button>
              <button
                type="submit"
                disabled={!valid}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#6395FF] text-[#0B0E11] disabled:bg-[#3D4A5C] disabled:text-[#7A8699] disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50"
              >
                저장
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

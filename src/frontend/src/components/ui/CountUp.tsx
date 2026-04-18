'use client';

import { useEffect, useRef, useState } from 'react';

type Props = {
  value: number;
  duration?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  separator?: string;
  forceSign?: boolean;
  className?: string;
};

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

function format(value: number, decimals: number, separator: string): string {
  let fixed = value.toFixed(decimals);
  if (separator) {
    const parts = fixed.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, separator);
    fixed = parts.join('.');
  }
  return fixed;
}

export default function CountUp({
  value,
  duration = 1200,
  decimals = 0,
  prefix = '',
  suffix = '',
  separator = '',
  forceSign = false,
  className,
}: Props) {
  const [display, setDisplay] = useState<string>(() => {
    const sign = value < 0 ? '-' : forceSign ? '+' : '';
    return prefix + sign + format(0, decimals, separator) + suffix;
  });
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!Number.isFinite(value)) return;

    const reducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    const sign = value < 0 ? '-' : forceSign ? '+' : '';
    const abs = Math.abs(value);

    if (reducedMotion) {
      // 이펙트 본문에서 즉시 setState 하면 React 19 react-hooks/set-state-in-effect 경고.
      // queueMicrotask 로 다음 micro task 에 실행해 렌더 완료 후 갱신 — 동일한 '즉시 최종값' UX 유지.
      const final = prefix + sign + format(abs, decimals, separator) + suffix;
      queueMicrotask(() => setDisplay(final));
      return;
    }

    const start = performance.now();
    const frame = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const v = abs * easeOutCubic(progress);
      setDisplay(prefix + sign + format(v, decimals, separator) + suffix);
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(frame);
      }
    };
    rafRef.current = requestAnimationFrame(frame);

    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [value, duration, decimals, prefix, suffix, separator, forceSign]);

  return <span className={className}>{display}</span>;
}

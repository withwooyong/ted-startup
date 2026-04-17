'use client';

import { useEffect, useRef, type ReactNode } from 'react';

type Props = {
  children: ReactNode;
  strength?: number;
  radius?: number;
  className?: string;
};

export default function Magnetic({
  children,
  strength = 0.25,
  radius = 1.3,
  className = '',
}: Props) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const coarsePointer = window.matchMedia('(pointer: coarse)').matches;
    if (reducedMotion || coarsePointer) return;

    let raf = 0;

    const move = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = e.clientX - cx;
      const dy = e.clientY - cy;
      const dist = Math.hypot(dx, dy);
      const trigger = Math.max(rect.width, rect.height) * radius;

      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        if (dist > trigger) {
          el.classList.remove('is-pulling');
          el.style.transform = '';
        } else {
          el.classList.add('is-pulling');
          el.style.transform = `translate(${(dx * strength).toFixed(1)}px, ${(dy * strength).toFixed(1)}px)`;
        }
      });
    };

    const reset = () => {
      cancelAnimationFrame(raf);
      el.classList.remove('is-pulling');
      el.style.transform = '';
    };

    el.addEventListener('mousemove', move);
    el.addEventListener('mouseleave', reset);

    return () => {
      cancelAnimationFrame(raf);
      el.removeEventListener('mousemove', move);
      el.removeEventListener('mouseleave', reset);
    };
  }, [strength, radius]);

  return (
    <span ref={ref} className={`magnetic ${className}`.trim()}>
      {children}
    </span>
  );
}

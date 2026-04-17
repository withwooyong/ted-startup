'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';

const NAV_ITEMS = [
  { href: '/', label: '대시보드' },
  { href: '/backtest', label: '백테스트' },
  { href: '/settings', label: '설정' },
];

export default function NavHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [prevPathname, setPrevPathname] = useState(pathname);

  // 경로 변경 시 메뉴 자동 닫힘 (render 중 상태 리셋 패턴)
  if (pathname !== prevPathname) {
    setPrevPathname(pathname);
    setOpen(false);
  }

  // ESC 키 지원
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  // exact match만 aria-current="page", sub-route 포함은 시각적 강조만
  const isExact = (href: string) => pathname === href;
  const isRelated = (href: string) =>
    href === '/' ? pathname === '/' || pathname.startsWith('/stocks') : pathname.startsWith(href);

  return (
    <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-[#0B0E11]/80 backdrop-blur">
      <nav
        aria-label="주 메뉴"
        className="max-w-6xl mx-auto px-5 h-14 flex items-center justify-between"
      >
        <Link
          href="/"
          className="font-[family-name:var(--font-display)] text-lg font-bold bg-gradient-to-r from-[#6395FF] to-[#a78bfa] bg-clip-text text-transparent"
        >
          SIGNAL
          <span className="text-[#3D4A5C] text-[0.65rem] font-normal ml-2 align-middle">v1.0</span>
        </Link>

        {/* Desktop nav */}
        <ul className="hidden sm:flex items-center gap-1">
          {NAV_ITEMS.map(item => (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={isExact(item.href) ? 'page' : undefined}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  isRelated(item.href)
                    ? 'text-[#E8ECF1] bg-white/[0.04]'
                    : 'text-[#6B7A90] hover:text-[#E8ECF1]'
                }`}
              >
                {item.label}
              </Link>
            </li>
          ))}
        </ul>

        {/* Hamburger (mobile only) */}
        <button
          type="button"
          aria-label={open ? '메뉴 닫기' : '메뉴 열기'}
          aria-expanded={open}
          aria-controls="mobile-menu"
          onClick={() => setOpen(o => !o)}
          className="sm:hidden p-2 -mr-2 rounded-lg text-[#6B7A90] hover:text-[#E8ECF1] focus:outline-none focus:ring-2 focus:ring-[#6395FF]/50"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            {open ? (
              <path d="M6 6l12 12M6 18L18 6" strokeLinecap="round" />
            ) : (
              <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
            )}
          </svg>
        </button>
      </nav>

      {/* Mobile drawer */}
      <div
        id="mobile-menu"
        hidden={!open}
        className="sm:hidden border-t border-white/[0.06] bg-[#0B0E11]"
      >
        <ul className="px-5 py-2">
          {NAV_ITEMS.map(item => (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={isExact(item.href) ? 'page' : undefined}
                className={`block px-3 py-3 rounded-lg text-sm ${
                  isRelated(item.href)
                    ? 'text-[#E8ECF1] bg-white/[0.04]'
                    : 'text-[#6B7A90]'
                }`}
              >
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </header>
  );
}

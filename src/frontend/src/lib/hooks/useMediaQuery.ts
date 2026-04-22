'use client';

import { useCallback, useSyncExternalStore } from 'react';

// useSyncExternalStore 로 matchMedia 를 구독한다. React 19 의
// `react-hooks/set-state-in-effect` 룰을 피하며 동시에 SSR-safe 하다.
// 서버 렌더 단계에서는 항상 `false` 를 반환 — 초기 페인트는 데스크톱 스타일로
// 나타났다가 클라이언트 hydration 직후 실제 매치값으로 전환된다. CSS 분기가
// 가능한 케이스는 CSS 로 처리하고, 본 훅은 recharts `aspect` 처럼 런타임
// 값이 필요한 경우에만 제한적으로 사용한다.
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (callback: () => void) => {
      const mql = window.matchMedia(query);
      mql.addEventListener('change', callback);
      return () => mql.removeEventListener('change', callback);
    },
    [query],
  );
  const getSnapshot = useCallback(() => window.matchMedia(query).matches, [query]);
  const getServerSnapshot = (): boolean => false;
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

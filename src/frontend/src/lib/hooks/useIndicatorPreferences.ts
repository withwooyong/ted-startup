'use client';

import { useCallback, useSyncExternalStore } from 'react';

// SSR-safe 로컬 저장 훅. Next 16 `react-hooks/set-state-in-effect` 규칙 회피를 위해
// useSyncExternalStore 로 구현. SSR 스냅샷은 DEFAULT_PREFS, 클라이언트 스냅샷은 localStorage.
// zod 미설치라 수동 타입 가드 사용.

export interface IndicatorPrefs {
  ma5: boolean;
  ma20: boolean;
  ma60: boolean;
  ma120: boolean;
  volume: boolean;
  rsi: boolean;
  macd: boolean;
}

export const DEFAULT_PREFS: IndicatorPrefs = {
  ma5: true,
  ma20: true,
  ma60: false,
  ma120: false,
  volume: true,
  rsi: false,
  macd: false,
};

const STORAGE_KEY = 'stock-chart-indicators:v1';

const PREF_KEYS: ReadonlyArray<keyof IndicatorPrefs> = [
  'ma5',
  'ma20',
  'ma60',
  'ma120',
  'volume',
  'rsi',
  'macd',
];

function isValidPrefs(v: unknown): v is IndicatorPrefs {
  if (!v || typeof v !== 'object') return false;
  const obj = v as Record<string, unknown>;
  return PREF_KEYS.every(k => typeof obj[k] === 'boolean');
}

// 같은 탭 내에서의 변경은 window.storage 이벤트를 발생시키지 않으므로,
// 인메모리 subscriber 집합으로 notify 한다.
const subscribers = new Set<() => void>();

function notify() {
  subscribers.forEach(cb => cb());
}

function subscribe(callback: () => void): () => void {
  subscribers.add(callback);
  const storageHandler = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) callback();
  };
  if (typeof window !== 'undefined') {
    window.addEventListener('storage', storageHandler);
  }
  return () => {
    subscribers.delete(callback);
    if (typeof window !== 'undefined') {
      window.removeEventListener('storage', storageHandler);
    }
  };
}

function getSnapshot(): IndicatorPrefs {
  if (typeof window === 'undefined') return DEFAULT_PREFS;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_PREFS;
    const parsed: unknown = JSON.parse(raw);
    return isValidPrefs(parsed) ? parsed : DEFAULT_PREFS;
  } catch {
    return DEFAULT_PREFS;
  }
}

function getServerSnapshot(): IndicatorPrefs {
  return DEFAULT_PREFS;
}

export function useIndicatorPreferences(): {
  prefs: IndicatorPrefs;
  setPref: <K extends keyof IndicatorPrefs>(key: K, value: boolean) => void;
} {
  const prefs = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const setPref = useCallback(
    <K extends keyof IndicatorPrefs>(key: K, value: boolean) => {
      if (typeof window === 'undefined') return;
      const current = getSnapshot();
      const next = { ...current, [key]: value };
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // quota exceeded / 프라이빗 모드 등 — notify 는 여전히 수행해서 UI 는 반응.
      }
      notify();
    },
    [],
  );

  return { prefs, setPref };
}

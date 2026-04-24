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
  bb: boolean;
}

export const DEFAULT_PREFS: IndicatorPrefs = {
  ma5: true,
  ma20: true,
  ma60: false,
  ma120: false,
  volume: true,
  rsi: false,
  macd: false,
  bb: false,
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
  'bb',
];

// v1.1 localStorage 에는 bb 필드가 없다. v1.2 Cp 1 에서는 전체 스키마를 v2 로
// 전환하지 않고 bb 만 추가 — v1 데이터에 bb 가 없으면 false 로 보정해 호환.
// (v1 → v2 전체 마이그레이션은 v1.2 Cp 2 에서.)
function isValidPrefs(v: unknown): v is Record<string, unknown> {
  if (!v || typeof v !== 'object') return false;
  const obj = v as Record<string, unknown>;
  return PREF_KEYS.filter(k => k !== 'bb').every(k => typeof obj[k] === 'boolean');
}

function coerceFromStored(raw: Record<string, unknown>): IndicatorPrefs {
  return {
    ma5: Boolean(raw.ma5),
    ma20: Boolean(raw.ma20),
    ma60: Boolean(raw.ma60),
    ma120: Boolean(raw.ma120),
    volume: Boolean(raw.volume),
    rsi: Boolean(raw.rsi),
    macd: Boolean(raw.macd),
    bb: typeof raw.bb === 'boolean' ? raw.bb : false,
  };
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

// useSyncExternalStore 는 snapshot 을 Object.is 로 비교해 동일하면 재렌더를 건너뛴다.
// JSON.parse 매번 새 객체를 반환하므로 raw 문자열을 키로 캐시해 동일 raw → 동일 객체 보장.
// (React #185 — Maximum update depth exceeded 방지)
let cachedRaw: string | null | undefined = undefined;
let cachedSnapshot: IndicatorPrefs = DEFAULT_PREFS;

function getSnapshot(): IndicatorPrefs {
  if (typeof window === 'undefined') return DEFAULT_PREFS;
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return cachedSnapshot;
  }
  if (raw === cachedRaw) return cachedSnapshot;
  cachedRaw = raw;
  if (!raw) {
    cachedSnapshot = DEFAULT_PREFS;
    return cachedSnapshot;
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    cachedSnapshot = isValidPrefs(parsed) ? coerceFromStored(parsed) : DEFAULT_PREFS;
  } catch {
    cachedSnapshot = DEFAULT_PREFS;
  }
  return cachedSnapshot;
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

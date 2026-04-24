'use client';

import { useCallback, useSyncExternalStore } from 'react';

// v1.2 Cp 2α — Indicator Preferences v2 스키마.
//
// 저장 위치: localStorage(`stock-chart-indicators:v2`). v1 키(`...:v1`) 가 남아있으면
// 최초 조회 시 v1 → v2 로 합성(migrateV1ToV2)해 DEFAULT_PARAMS 를 입히고,
// 첫 쓰기 시 v2 로 저장 + v1 키 삭제 (1 회성 정리).
//
// Next 16 `react-hooks/set-state-in-effect` 규칙 회피를 위해 useSyncExternalStore 사용.
// snapshot 캐시 필수(v1.1 hotfix 669d9e8 교훈) — getSnapshot 이 매번 새 객체를 반환하면
// React #185 Maximum update depth exceeded 발생.
//
// Cp 3 에서 DB 동기화 어댑터(`preferences-sync.ts`) 가 setPrefs 로 서버 페이로드 일괄
// 주입할 수 있도록 API 에 setPrefs 포함.

export interface IndicatorToggles {
  ma5: boolean;
  ma20: boolean;
  ma60: boolean;
  ma120: boolean;
  volume: boolean;
  rsi: boolean;
  macd: boolean;
  bb: boolean;
}

export type MaWindows = readonly [number, number, number, number];

export interface RsiParams {
  period: number;
  overbought: number;
  oversold: number;
}

export interface MacdParams {
  fast: number;
  slow: number;
  signal: number;
}

export interface BbParams {
  period: number;
  k: number;
}

export interface IndicatorParams {
  ma: MaWindows;
  rsi: RsiParams;
  macd: MacdParams;
  bb: BbParams;
}

export interface IndicatorPrefs {
  schema_version: 2;
  toggles: IndicatorToggles;
  params: IndicatorParams;
}

export const DEFAULT_TOGGLES: IndicatorToggles = {
  ma5: true,
  ma20: true,
  ma60: false,
  ma120: false,
  volume: true,
  rsi: false,
  macd: false,
  bb: false,
};

export const DEFAULT_PARAMS: IndicatorParams = {
  ma: [5, 20, 60, 120] as const,
  rsi: { period: 14, overbought: 70, oversold: 30 },
  macd: { fast: 12, slow: 26, signal: 9 },
  bb: { period: 20, k: 2 },
};

export const DEFAULT_PREFS: IndicatorPrefs = {
  schema_version: 2,
  toggles: DEFAULT_TOGGLES,
  params: DEFAULT_PARAMS,
};

const STORAGE_KEY_V1 = 'stock-chart-indicators:v1';
const STORAGE_KEY_V2 = 'stock-chart-indicators:v2';

const TOGGLE_KEYS: ReadonlyArray<keyof IndicatorToggles> = [
  'ma5',
  'ma20',
  'ma60',
  'ma120',
  'volume',
  'rsi',
  'macd',
  'bb',
];

function isObj(v: unknown): v is Record<string, unknown> {
  return !!v && typeof v === 'object' && !Array.isArray(v);
}

function isPositiveInt(v: unknown, min = 1): v is number {
  return typeof v === 'number' && Number.isInteger(v) && v >= min;
}

function isPositiveFinite(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v) && v > 0;
}

/**
 * v2 스키마 검증 — 엄격 가드. 실패 시 호출자가 DEFAULT_PREFS 로 fallback.
 * 필드 누락/타입 오류/경계 위반이 하나라도 있으면 false.
 */
export function isValidPrefsV2(v: unknown): v is IndicatorPrefs {
  if (!isObj(v)) return false;
  if (v.schema_version !== 2) return false;

  if (!isObj(v.toggles)) return false;
  const t = v.toggles;
  if (!TOGGLE_KEYS.every(k => typeof t[k] === 'boolean')) return false;

  if (!isObj(v.params)) return false;
  const p = v.params;

  if (!Array.isArray(p.ma) || p.ma.length !== 4) return false;
  if (!(p.ma as unknown[]).every(n => isPositiveInt(n, 2))) return false;

  if (!isObj(p.rsi)) return false;
  const rsi = p.rsi;
  if (!isPositiveInt(rsi.period, 2)) return false;
  if (!isPositiveInt(rsi.overbought, 1)) return false;
  if (!isPositiveInt(rsi.oversold, 1)) return false;
  if (rsi.overbought <= rsi.oversold) return false;

  if (!isObj(p.macd)) return false;
  const macd = p.macd;
  if (!isPositiveInt(macd.fast, 2)) return false;
  if (!isPositiveInt(macd.slow, 2)) return false;
  if (!isPositiveInt(macd.signal, 2)) return false;
  if (macd.fast >= macd.slow) return false;

  if (!isObj(p.bb)) return false;
  const bb = p.bb;
  if (!isPositiveInt(bb.period, 2)) return false;
  if (!isPositiveFinite(bb.k)) return false;

  return true;
}

/**
 * v1 레거시 구조 (flat 7-boolean 토글) → v2 합성.
 * 파라미터 필드가 v1 에 없으므로 DEFAULT_PARAMS 주입. 토글은 v1 값 그대로 이식.
 */
export function migrateV1ToV2(raw: unknown): IndicatorPrefs {
  const toggles: IndicatorToggles = { ...DEFAULT_TOGGLES };
  if (isObj(raw)) {
    for (const k of TOGGLE_KEYS) {
      if (typeof raw[k] === 'boolean') toggles[k] = raw[k] as boolean;
    }
  }
  return {
    schema_version: 2,
    toggles,
    params: DEFAULT_PARAMS,
  };
}

// 인메모리 subscriber — 같은 탭 내 쓰기는 storage 이벤트가 발생하지 않으므로 수동 notify.
const subscribers = new Set<() => void>();

function notify() {
  subscribers.forEach(cb => cb());
}

function subscribe(callback: () => void): () => void {
  subscribers.add(callback);
  const storageHandler = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY_V2 || e.key === STORAGE_KEY_V1) callback();
  };
  /* v8 ignore next 3 — SSR 가드, jsdom 에서는 항상 true */
  if (typeof window !== 'undefined') {
    window.addEventListener('storage', storageHandler);
  }
  return () => {
    subscribers.delete(callback);
    /* v8 ignore next 3 */
    if (typeof window !== 'undefined') {
      window.removeEventListener('storage', storageHandler);
    }
  };
}

// snapshot 캐시 — raw 문자열 동일 시 동일 객체 반환 (Object.is 통과 → 재렌더 스킵).
let cachedKey: string | undefined = undefined;
let cachedSnapshot: IndicatorPrefs = DEFAULT_PREFS;

function readRaw(): { source: 'v2' | 'v1' | 'none'; raw: string | null } {
  /* v8 ignore next — SSR 가드 */
  if (typeof window === 'undefined') return { source: 'none', raw: null };
  try {
    const v2 = window.localStorage.getItem(STORAGE_KEY_V2);
    if (v2) return { source: 'v2', raw: v2 };
    const v1 = window.localStorage.getItem(STORAGE_KEY_V1);
    if (v1) return { source: 'v1', raw: v1 };
    return { source: 'none', raw: null };
  } catch {
    return { source: 'none', raw: null };
  }
}

function getSnapshot(): IndicatorPrefs {
  // readRaw 가 SSR(window 없음) 과 접근 예외를 source='none' 으로 정규화.
  const { source, raw } = readRaw();
  const key = `${source}:${raw ?? ''}`;
  if (key === cachedKey) return cachedSnapshot;
  cachedKey = key;

  if (source === 'none' || !raw) {
    cachedSnapshot = DEFAULT_PREFS;
    return cachedSnapshot;
  }

  try {
    const parsed: unknown = JSON.parse(raw);
    if (source === 'v2') {
      cachedSnapshot = isValidPrefsV2(parsed) ? (parsed as IndicatorPrefs) : DEFAULT_PREFS;
    } else {
      cachedSnapshot = migrateV1ToV2(parsed);
    }
  } catch {
    cachedSnapshot = DEFAULT_PREFS;
  }
  return cachedSnapshot;
}

/* v8 ignore start — SSR 경로는 jsdom 에서 도달 불가, 런타임 행동은 단순 기본값 반환 */
function getServerSnapshot(): IndicatorPrefs {
  return DEFAULT_PREFS;
}
/* v8 ignore stop */

function writePrefs(next: IndicatorPrefs): void {
  /* v8 ignore next — 이벤트 핸들러에서만 호출되므로 client-side 에서만 실행 */
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY_V2, JSON.stringify(next));
    // v1 키가 존재하면 최초 v2 저장 시 정리 (멱등).
    window.localStorage.removeItem(STORAGE_KEY_V1);
  } catch {
    // quota / 프라이빗 모드 등 — 저장 실패해도 notify 는 발생시켜 UI 는 반응.
  }
  notify();
}

export function useIndicatorPreferences(): {
  prefs: IndicatorPrefs;
  setToggle: <K extends keyof IndicatorToggles>(key: K, value: boolean) => void;
  setParams: (params: IndicatorParams) => void;
  setPrefs: (prefs: IndicatorPrefs) => void;
} {
  const prefs = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const setToggle = useCallback(
    <K extends keyof IndicatorToggles>(key: K, value: boolean) => {
      const current = getSnapshot();
      writePrefs({ ...current, toggles: { ...current.toggles, [key]: value } });
    },
    [],
  );

  const setParams = useCallback((params: IndicatorParams) => {
    const current = getSnapshot();
    writePrefs({ ...current, params });
  }, []);

  const setPrefs = useCallback((next: IndicatorPrefs) => {
    writePrefs(next);
  }, []);

  return { prefs, setToggle, setParams, setPrefs };
}

// ─────────────────────────────────────────────────────────────────────────────
// 테스트 전용 — 모듈 스코프 캐시/subscriber 를 리셋. 프로덕션 경로에서는 호출되지 않음.
export function __resetForTesting__(): void {
  cachedKey = undefined;
  cachedSnapshot = DEFAULT_PREFS;
  subscribers.clear();
}

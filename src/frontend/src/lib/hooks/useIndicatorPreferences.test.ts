import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  DEFAULT_PARAMS,
  DEFAULT_PREFS,
  DEFAULT_TOGGLES,
  __resetForTesting__,
  isValidPrefsV2,
  migrateV1ToV2,
  useIndicatorPreferences,
  type IndicatorPrefs,
} from './useIndicatorPreferences';

const STORAGE_KEY_V1 = 'stock-chart-indicators:v1';
const STORAGE_KEY_V2 = 'stock-chart-indicators:v2';

function clone<T>(v: T): T {
  return JSON.parse(JSON.stringify(v));
}

beforeEach(() => {
  window.localStorage.clear();
  __resetForTesting__();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ─── isValidPrefsV2 ────────────────────────────────────────────────────────

describe('isValidPrefsV2', () => {
  it('accepts a full valid v2 payload', () => {
    expect(isValidPrefsV2(clone(DEFAULT_PREFS))).toBe(true);
  });

  it('rejects non-objects and arrays', () => {
    expect(isValidPrefsV2(null)).toBe(false);
    expect(isValidPrefsV2(undefined)).toBe(false);
    expect(isValidPrefsV2(42)).toBe(false);
    expect(isValidPrefsV2('string')).toBe(false);
    expect(isValidPrefsV2([])).toBe(false);
  });

  it('rejects wrong schema_version', () => {
    const p = clone(DEFAULT_PREFS);
    (p as unknown as { schema_version: number }).schema_version = 1;
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects missing toggle key', () => {
    const p = clone(DEFAULT_PREFS) as unknown as { toggles: Record<string, unknown> };
    delete p.toggles.bb;
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects non-boolean toggle', () => {
    const p = clone(DEFAULT_PREFS) as unknown as { toggles: Record<string, unknown> };
    p.toggles.rsi = 'yes';
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects missing params section', () => {
    const p = clone(DEFAULT_PREFS) as unknown as Record<string, unknown>;
    delete p.params;
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects ma array with wrong length', () => {
    const p = clone(DEFAULT_PREFS);
    (p.params as unknown as { ma: number[] }).ma = [5, 20, 60];
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects ma with non-integer window', () => {
    const p = clone(DEFAULT_PREFS);
    (p.params as unknown as { ma: number[] }).ma = [5, 20, 60, 0];
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects rsi missing overbought', () => {
    const p = clone(DEFAULT_PREFS) as unknown as { params: { rsi: Record<string, unknown> } };
    delete p.params.rsi.overbought;
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects rsi non-object', () => {
    const p = clone(DEFAULT_PREFS) as unknown as { params: { rsi: unknown } };
    p.params.rsi = null;
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects rsi period < 2', () => {
    const p = clone(DEFAULT_PREFS);
    p.params.rsi = { period: 1, overbought: 70, oversold: 30 };
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects rsi zero oversold', () => {
    const p = clone(DEFAULT_PREFS);
    p.params.rsi = { period: 14, overbought: 70, oversold: 0 };
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects macd non-object', () => {
    const p = clone(DEFAULT_PREFS) as unknown as { params: { macd: unknown } };
    p.params.macd = null;
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects macd fast non-integer', () => {
    const p = clone(DEFAULT_PREFS);
    (p.params as unknown as { macd: Record<string, unknown> }).macd = {
      fast: 'foo', slow: 26, signal: 9,
    };
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects macd slow invalid when fast valid', () => {
    const p = clone(DEFAULT_PREFS);
    p.params.macd = { fast: 3, slow: 1, signal: 9 };
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects macd signal invalid when fast/slow valid', () => {
    const p = clone(DEFAULT_PREFS);
    p.params.macd = { fast: 3, slow: 10, signal: 0 };
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects rsi overbought <= oversold (MACD fast<slow 과 평행한 교차 검증)', () => {
    const p = clone(DEFAULT_PREFS);
    p.params.rsi = { period: 14, overbought: 30, oversold: 70 };
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects macd fast >= slow', () => {
    const p = clone(DEFAULT_PREFS);
    p.params.macd = { fast: 26, slow: 12, signal: 9 };
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects macd with zero signal', () => {
    const p = clone(DEFAULT_PREFS);
    p.params.macd = { fast: 12, slow: 26, signal: 0 };
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects bb with non-positive k', () => {
    const p = clone(DEFAULT_PREFS);
    p.params.bb = { period: 20, k: 0 };
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects bb with non-integer period', () => {
    const p = clone(DEFAULT_PREFS);
    p.params.bb = { period: 1, k: 2 };
    expect(isValidPrefsV2(p)).toBe(false);
  });

  it('rejects non-object params.bb', () => {
    const p = clone(DEFAULT_PREFS) as unknown as { params: { bb: unknown } };
    p.params.bb = null;
    expect(isValidPrefsV2(p)).toBe(false);
  });
});

// ─── migrateV1ToV2 ─────────────────────────────────────────────────────────

describe('migrateV1ToV2', () => {
  it('migrates full v1 shape preserving toggle booleans', () => {
    const v1 = {
      ma5: true, ma20: false, ma60: true, ma120: true,
      volume: false, rsi: true, macd: false,
    };
    const v2 = migrateV1ToV2(v1);
    expect(v2.schema_version).toBe(2);
    expect(v2.toggles.ma5).toBe(true);
    expect(v2.toggles.ma20).toBe(false);
    expect(v2.toggles.macd).toBe(false);
    expect(v2.toggles.bb).toBe(false); // v1 에 없으므로 DEFAULT_TOGGLES.bb
    expect(v2.params).toEqual(DEFAULT_PARAMS);
  });

  it('partial v1 keys keep DEFAULT_TOGGLES for missing', () => {
    const v1 = { ma5: false, volume: false };
    const v2 = migrateV1ToV2(v1);
    expect(v2.toggles.ma5).toBe(false);
    expect(v2.toggles.volume).toBe(false);
    expect(v2.toggles.ma20).toBe(DEFAULT_TOGGLES.ma20); // default true
  });

  it('non-object raw falls back to DEFAULT_PREFS', () => {
    const v2 = migrateV1ToV2(null);
    expect(v2).toEqual(DEFAULT_PREFS);
  });

  it('non-boolean values are ignored (defaults preserved)', () => {
    const v1 = { ma5: 'yes', rsi: 1 };
    const v2 = migrateV1ToV2(v1);
    expect(v2.toggles.ma5).toBe(DEFAULT_TOGGLES.ma5);
    expect(v2.toggles.rsi).toBe(DEFAULT_TOGGLES.rsi);
  });
});

// ─── useIndicatorPreferences (hook) ────────────────────────────────────────

describe('useIndicatorPreferences', () => {
  it('returns DEFAULT_PREFS on empty storage', () => {
    const { result } = renderHook(() => useIndicatorPreferences());
    expect(result.current.prefs).toEqual(DEFAULT_PREFS);
  });

  it('loads valid v2 from localStorage', () => {
    const stored: IndicatorPrefs = {
      ...clone(DEFAULT_PREFS),
      toggles: { ...DEFAULT_TOGGLES, bb: true, rsi: true },
    };
    window.localStorage.setItem(STORAGE_KEY_V2, JSON.stringify(stored));

    const { result } = renderHook(() => useIndicatorPreferences());
    expect(result.current.prefs.toggles.bb).toBe(true);
    expect(result.current.prefs.toggles.rsi).toBe(true);
  });

  it('falls back to DEFAULT on invalid JSON', () => {
    window.localStorage.setItem(STORAGE_KEY_V2, '{not-json');
    const { result } = renderHook(() => useIndicatorPreferences());
    expect(result.current.prefs).toEqual(DEFAULT_PREFS);
  });

  it('falls back to DEFAULT on invalid v2 shape', () => {
    window.localStorage.setItem(STORAGE_KEY_V2, JSON.stringify({ schema_version: 2 }));
    const { result } = renderHook(() => useIndicatorPreferences());
    expect(result.current.prefs).toEqual(DEFAULT_PREFS);
  });

  it('migrates v1 → v2 when only v1 key exists', () => {
    const v1 = {
      ma5: false, ma20: true, ma60: true, ma120: false,
      volume: false, rsi: true, macd: false,
    };
    window.localStorage.setItem(STORAGE_KEY_V1, JSON.stringify(v1));

    const { result } = renderHook(() => useIndicatorPreferences());
    expect(result.current.prefs.toggles.ma5).toBe(false);
    expect(result.current.prefs.toggles.rsi).toBe(true);
    expect(result.current.prefs.toggles.bb).toBe(false);
    expect(result.current.prefs.params).toEqual(DEFAULT_PARAMS);
  });

  it('prefers v2 key when both v1 and v2 present', () => {
    const v1 = { ma5: false, ma20: false, ma60: false, ma120: false, volume: false, rsi: false, macd: false };
    const v2: IndicatorPrefs = {
      ...clone(DEFAULT_PREFS),
      toggles: { ...DEFAULT_TOGGLES, ma5: true },
    };
    window.localStorage.setItem(STORAGE_KEY_V1, JSON.stringify(v1));
    window.localStorage.setItem(STORAGE_KEY_V2, JSON.stringify(v2));

    const { result } = renderHook(() => useIndicatorPreferences());
    expect(result.current.prefs.toggles.ma5).toBe(true); // v2 우선
  });

  it('setToggle updates localStorage and snapshot', () => {
    const { result } = renderHook(() => useIndicatorPreferences());
    act(() => result.current.setToggle('bb', true));

    expect(result.current.prefs.toggles.bb).toBe(true);
    const raw = window.localStorage.getItem(STORAGE_KEY_V2);
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!) as IndicatorPrefs;
    expect(parsed.toggles.bb).toBe(true);
  });

  it('setToggle removes stale v1 key (1회성 정리)', () => {
    const v1 = { ma5: true, ma20: true, ma60: false, ma120: false, volume: true, rsi: false, macd: false };
    window.localStorage.setItem(STORAGE_KEY_V1, JSON.stringify(v1));

    const { result } = renderHook(() => useIndicatorPreferences());
    act(() => result.current.setToggle('bb', true));

    expect(window.localStorage.getItem(STORAGE_KEY_V1)).toBeNull();
    expect(window.localStorage.getItem(STORAGE_KEY_V2)).toBeTruthy();
  });

  it('setParams updates params and preserves toggles', () => {
    const { result } = renderHook(() => useIndicatorPreferences());
    const newParams = {
      ...DEFAULT_PARAMS,
      rsi: { period: 9, overbought: 80, oversold: 20 },
    };
    act(() => result.current.setParams(newParams));

    expect(result.current.prefs.params.rsi.period).toBe(9);
    expect(result.current.prefs.toggles).toEqual(DEFAULT_TOGGLES);
  });

  it('setPrefs replaces entire object (DB adapter scenario)', () => {
    const { result } = renderHook(() => useIndicatorPreferences());
    const custom: IndicatorPrefs = {
      schema_version: 2,
      toggles: { ...DEFAULT_TOGGLES, bb: true, ma60: true },
      params: { ...DEFAULT_PARAMS, bb: { period: 30, k: 2.5 } },
    };
    act(() => result.current.setPrefs(custom));

    expect(result.current.prefs.toggles.bb).toBe(true);
    expect(result.current.prefs.toggles.ma60).toBe(true);
    expect(result.current.prefs.params.bb).toEqual({ period: 30, k: 2.5 });
  });

  it('multi-subscriber sync — second hook sees first hook write', () => {
    const { result: a } = renderHook(() => useIndicatorPreferences());
    const { result: b } = renderHook(() => useIndicatorPreferences());
    act(() => a.current.setToggle('rsi', true));
    expect(b.current.prefs.toggles.rsi).toBe(true);
  });

  it('snapshot cache returns stable reference for unchanged raw', () => {
    const { result, rerender } = renderHook(() => useIndicatorPreferences());
    const first = result.current.prefs;
    rerender();
    const second = result.current.prefs;
    expect(second).toBe(first); // Object.is
  });

  it('responds to cross-tab storage event', () => {
    const { result } = renderHook(() => useIndicatorPreferences());
    const stored: IndicatorPrefs = {
      ...clone(DEFAULT_PREFS),
      toggles: { ...DEFAULT_TOGGLES, macd: true },
    };

    act(() => {
      window.localStorage.setItem(STORAGE_KEY_V2, JSON.stringify(stored));
      window.dispatchEvent(
        new StorageEvent('storage', { key: STORAGE_KEY_V2, newValue: JSON.stringify(stored) }),
      );
    });

    expect(result.current.prefs.toggles.macd).toBe(true);
  });

  it('ignores storage events for unrelated keys', () => {
    const { result } = renderHook(() => useIndicatorPreferences());
    act(() => {
      window.dispatchEvent(new StorageEvent('storage', { key: 'some-other-key' }));
    });
    // 미해당 키는 notify 가 일어나지 않아 스냅샷 변화 없음.
    expect(result.current.prefs).toEqual(DEFAULT_PREFS);
  });

  it('falls back to cachedSnapshot when localStorage throws on read', () => {
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied');
    });
    const { result } = renderHook(() => useIndicatorPreferences());
    expect(result.current.prefs).toEqual(DEFAULT_PREFS);
    spy.mockRestore();
  });

  it('setToggle does not throw when localStorage.setItem throws', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota');
    });
    const { result } = renderHook(() => useIndicatorPreferences());
    expect(() => act(() => result.current.setToggle('bb', true))).not.toThrow();
    spy.mockRestore();
  });

  it('unsubscribes storage listener on unmount', () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener');
    const { unmount } = renderHook(() => useIndicatorPreferences());
    unmount();
    expect(removeSpy).toHaveBeenCalledWith('storage', expect.any(Function));
  });
});

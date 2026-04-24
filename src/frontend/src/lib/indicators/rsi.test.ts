import { describe, expect, it } from 'vitest';
import { rsi } from './rsi';

describe('rsi', () => {
  it('throws on non-positive or non-integer period', () => {
    expect(() => rsi([1, 2, 3], 0)).toThrow(/positive integer/);
    expect(() => rsi([1, 2, 3], -5)).toThrow(/positive integer/);
    expect(() => rsi([1, 2, 3], 2.5)).toThrow(/positive integer/);
  });

  it('returns empty array for empty input', () => {
    expect(rsi([], 14)).toEqual([]);
  });

  it('preserves input length', () => {
    const n = 40;
    const values = Array.from({ length: n }, (_, i) => 100 + i);
    expect(rsi(values, 14)).toHaveLength(n);
  });

  it('returns all NaN when input length <= period', () => {
    // For period=14, need at least period+1 prior points to emit a value
    const out = rsi([1, 2, 3, 4, 5], 14);
    expect(out.every(Number.isNaN)).toBe(true);
  });

  it('leaves first `period` indices NaN (inclusive)', () => {
    const values = Array.from({ length: 20 }, (_, i) => i + 1);
    const out = rsi(values, 5);
    for (let i = 0; i < 5; i++) expect(out[i]).toBeNaN();
    expect(Number.isFinite(out[5])).toBe(true);
  });

  it('strictly monotonic increasing series yields RSI 100 at first valid index', () => {
    const values = Array.from({ length: 20 }, (_, i) => i + 1);
    const out = rsi(values, 5);
    expect(out[5]).toBe(100);
  });

  it('strictly monotonic decreasing series yields RSI close to 0', () => {
    const values = Array.from({ length: 20 }, (_, i) => 100 - i);
    const out = rsi(values, 5);
    // avgGain=0 → 100 - 100/(1 + 0) = 0
    expect(out[5]).toBe(0);
  });

  it('mixed up/down series yields RSI in (0, 100)', () => {
    const values = [10, 11, 10.5, 11.5, 11, 12, 11.5, 12.5, 12, 13, 12.5, 13.5, 13, 14, 13.5, 14.5, 14, 15];
    const out = rsi(values, 14);
    const valid = out.filter(Number.isFinite);
    expect(valid.length).toBeGreaterThan(0);
    for (const v of valid) {
      expect(v).toBeGreaterThan(0);
      expect(v).toBeLessThan(100);
    }
  });

  it('uses default period=14 when not provided', () => {
    const values = Array.from({ length: 30 }, (_, i) => i + 1);
    const out = rsi(values);
    expect(out[14]).toBe(100);
    for (let i = 0; i < 14; i++) expect(out[i]).toBeNaN();
  });
});

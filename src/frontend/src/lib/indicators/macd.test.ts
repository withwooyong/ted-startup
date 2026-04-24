import { describe, expect, it } from 'vitest';
import { macd } from './macd';

describe('macd', () => {
  it('throws on invalid fast', () => {
    expect(() => macd([1, 2, 3], 0, 26, 9)).toThrow(/fast/);
    expect(() => macd([1, 2, 3], -1, 26, 9)).toThrow(/fast/);
    expect(() => macd([1, 2, 3], 1.5, 26, 9)).toThrow(/fast/);
  });

  it('throws when slow is not > fast', () => {
    expect(() => macd([1, 2, 3], 12, 12, 9)).toThrow(/slow/);
    expect(() => macd([1, 2, 3], 12, 10, 9)).toThrow(/slow/);
  });

  it('throws on invalid signalPeriod', () => {
    expect(() => macd([1, 2, 3], 12, 26, 0)).toThrow(/signalPeriod/);
    expect(() => macd([1, 2, 3], 12, 26, -3)).toThrow(/signalPeriod/);
  });

  it('returns arrays equal to input length', () => {
    const n = 60;
    const values = Array.from({ length: n }, (_, i) => 100 + Math.sin(i / 5) * 3);
    const { macd: line, signal, histogram } = macd(values, 12, 26, 9);
    expect(line).toHaveLength(n);
    expect(signal).toHaveLength(n);
    expect(histogram).toHaveLength(n);
  });

  it('returns all NaN when input is shorter than slow', () => {
    const { macd: line, signal, histogram } = macd([1, 2, 3, 4, 5], 12, 26, 9);
    expect(line.every(Number.isNaN)).toBe(true);
    expect(signal.every(Number.isNaN)).toBe(true);
    expect(histogram.every(Number.isNaN)).toBe(true);
  });

  it('histogram equals macd - signal on valid indices', () => {
    const values = Array.from({ length: 80 }, (_, i) => 100 + i * 0.5 + Math.sin(i / 4));
    const { macd: line, signal, histogram } = macd(values, 12, 26, 9);
    for (let i = 0; i < values.length; i++) {
      if (Number.isFinite(line[i]) && Number.isFinite(signal[i])) {
        expect(histogram[i]).toBeCloseTo(line[i] - signal[i], 10);
      } else {
        expect(histogram[i]).toBeNaN();
      }
    }
  });

  it('monotonic increasing series → eventually positive macd', () => {
    const values = Array.from({ length: 80 }, (_, i) => i + 1);
    const { macd: line } = macd(values, 12, 26, 9);
    // find first finite index
    const idx = line.findIndex(Number.isFinite);
    expect(idx).toBeGreaterThan(0);
    expect(line[line.length - 1]).toBeGreaterThan(0);
  });

  it('uses default (12, 26, 9) when omitted', () => {
    const values = Array.from({ length: 60 }, (_, i) => 100 + i);
    const r1 = macd(values);
    const r2 = macd(values, 12, 26, 9);
    expect(r1.macd).toEqual(r2.macd);
    expect(r1.signal).toEqual(r2.signal);
    expect(r1.histogram).toEqual(r2.histogram);
  });

  it('first valid macd index is at slow-1 (since slow EMA seeds there)', () => {
    const values = Array.from({ length: 40 }, (_, i) => 100 + i);
    const { macd: line } = macd(values, 5, 10, 3);
    for (let i = 0; i < 9; i++) expect(line[i]).toBeNaN();
    expect(Number.isFinite(line[9])).toBe(true);
  });
});

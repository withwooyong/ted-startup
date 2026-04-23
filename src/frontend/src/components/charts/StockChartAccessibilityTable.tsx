import type { CandlePoint } from '@/components/charts/PriceAreaChart';

interface Props {
  data: ReadonlyArray<CandlePoint>;
  volumes: ReadonlyArray<number>; // length == data.length
  ma5: ReadonlyArray<number>;
  ma20: ReadonlyArray<number>;
  rsi: ReadonlyArray<number>;
  macd: ReadonlyArray<number>;
}

// sr-only 대체 테이블 — 스크린리더 사용자용 OHLCV + 주요 지표 값 (최근 30 거래일).
// 차트의 canvas 는 aria-hidden 이므로 이 테이블이 유일한 AT 채널.

const ROW_LIMIT = 30;

function fmt(v: number | undefined | null, digits = 0): string {
  if (v == null || !Number.isFinite(v)) return '-';
  return v.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export default function StockChartAccessibilityTable({
  data,
  volumes,
  ma5,
  ma20,
  rsi,
  macd,
}: Props) {
  if (data.length === 0) return null;
  const start = Math.max(0, data.length - ROW_LIMIT);
  const rows = data.slice(start);

  return (
    <table className="sr-only" aria-label="최근 30 거래일 가격 및 지표">
      <caption>최근 {rows.length} 거래일의 OHLCV 및 보조 지표 값</caption>
      <thead>
        <tr>
          <th scope="col">일자</th>
          <th scope="col">시가</th>
          <th scope="col">고가</th>
          <th scope="col">저가</th>
          <th scope="col">종가</th>
          <th scope="col">거래량</th>
          <th scope="col">MA5</th>
          <th scope="col">MA20</th>
          <th scope="col">RSI(14)</th>
          <th scope="col">MACD</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, idx) => {
          const i = start + idx;
          return (
            <tr key={r.date}>
              <th scope="row">{r.date}</th>
              <td>{fmt(r.open)}</td>
              <td>{fmt(r.high)}</td>
              <td>{fmt(r.low)}</td>
              <td>{fmt(r.close)}</td>
              <td>{fmt(volumes[i])}</td>
              <td>{fmt(ma5[i], 2)}</td>
              <td>{fmt(ma20[i], 2)}</td>
              <td>{fmt(rsi[i], 2)}</td>
              <td>{fmt(macd[i], 2)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

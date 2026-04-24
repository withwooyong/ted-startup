import { http, HttpResponse, delay } from 'msw';

const ENDPOINT = '/api/admin/indicator-preferences';

export const defaultPayload = {
  schema_version: 2,
  toggles: {
    ma5: true, ma20: true, ma60: false, ma120: false,
    volume: true, rsi: false, macd: false, bb: false,
  },
  params: {
    ma: [5, 20, 60, 120] as [number, number, number, number],
    rsi: { period: 14, overbought: 70, oversold: 30 },
    macd: { fast: 12, slow: 26, signal: 9 },
    bb: { period: 20, k: 2 },
  },
  dirty: false,
  updated_at: '2026-04-24T00:00:00Z',
};

export const handlers = [
  http.get(ENDPOINT, () => HttpResponse.json(defaultPayload)),
  http.put(ENDPOINT, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ ...body, updated_at: new Date().toISOString() });
  }),
];

export const errorHandlers = {
  get400: http.get(ENDPOINT, () =>
    HttpResponse.json({ status: 400, message: 'invalid payload' }, { status: 400 }),
  ),
  get500: http.get(ENDPOINT, () =>
    HttpResponse.json({ status: 500, message: 'internal error' }, { status: 500 }),
  ),
  put400: http.put(ENDPOINT, () =>
    HttpResponse.json({ status: 400, message: 'validation failed' }, { status: 400 }),
  ),
  put500: http.put(ENDPOINT, () =>
    HttpResponse.json({ status: 500, message: 'internal error' }, { status: 500 }),
  ),
  networkError: http.put(ENDPOINT, async () => {
    await delay(10);
    return HttpResponse.error();
  }),
};

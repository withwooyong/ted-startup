import { test, expect } from '@playwright/test';

test.describe('H. 백테스트', () => {
  test('H1: /backtest → h1 "Backtest Results"', async ({ page }) => {
    await page.goto('/backtest');

    await expect(
      page.getByRole('heading', { level: 1, name: 'Backtest Results' }),
    ).toBeVisible();
  });

  test('H2: backtest 0건 (빈 응답 stub) → empty state', async ({ page }) => {
    // 미래에 실제 데이터가 생겨도 테스트가 깨지지 않도록 응답을 stub 처리.
    await page.route('**/api/backtest', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      }),
    );

    await page.goto('/backtest');

    await expect(page.getByText('백테스팅을 아직 실행하지 않았어요')).toBeVisible({
      timeout: 10_000,
    });
  });

  test('H3: backtest 3종 응답 stub → 기간 카피 + 차트 영역 렌더', async ({ page }) => {
    const fixture = [
      {
        id: 1,
        signal_type: 'RAPID_DECLINE',
        period_start: '2025-01-01',
        period_end: '2026-04-15',
        total_signals: 1234,
        hit_count_5d: 820, hit_rate_5d: '66.4500', avg_return_5d: '2.1300',
        hit_count_10d: 780, hit_rate_10d: '63.2100', avg_return_10d: '3.8700',
        hit_count_20d: 690, hit_rate_20d: '55.9100', avg_return_20d: '5.4200',
        created_at: '2026-04-15T09:00:00+09:00',
      },
      {
        id: 2,
        signal_type: 'TREND_REVERSAL',
        period_start: '2025-01-01',
        period_end: '2026-04-15',
        total_signals: 567,
        hit_count_5d: 310, hit_rate_5d: '54.6700', avg_return_5d: '1.2200',
        hit_count_10d: 295, hit_rate_10d: '52.0500', avg_return_10d: '2.4500',
        hit_count_20d: 270, hit_rate_20d: '47.6100', avg_return_20d: '3.1800',
        created_at: '2026-04-15T09:00:00+09:00',
      },
      {
        id: 3,
        signal_type: 'SHORT_SQUEEZE',
        period_start: '2025-01-01',
        period_end: '2026-04-15',
        total_signals: 2345,
        hit_count_5d: 1500, hit_rate_5d: '63.9700', avg_return_5d: '2.8900',
        hit_count_10d: 1420, hit_rate_10d: '60.5500', avg_return_10d: '4.7200',
        hit_count_20d: 1280, hit_rate_20d: '54.5800', avg_return_20d: '6.9300',
        created_at: '2026-04-15T09:00:00+09:00',
      },
    ];

    await page.route('**/api/backtest', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(fixture),
      }),
    );

    await page.goto('/backtest');

    await expect(page.getByText('2025-01-01 — 2026-04-15')).toBeVisible({ timeout: 10_000 });
    // Empty state 는 더 이상 노출되지 않음
    await expect(page.getByText('백테스팅을 아직 실행하지 않았어요')).toHaveCount(0);
  });

  test('H4: backtest API 500 → 재시도 버튼 노출', async ({ page }) => {
    await page.route('**/api/backtest', route =>
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'internal' }),
      }),
    );

    await page.goto('/backtest');

    await expect(page.getByRole('button', { name: '다시 시도' })).toBeVisible({
      timeout: 10_000,
    });
  });

  test('H5: 실데이터 — 3개 SignalType 라벨 + 차트 렌더', async ({ page }) => {
    // scripts/seed_backtest_e2e 가 선행돼 backtest_result 3행이 적재된 상태 가정.
    // stub 없이 실제 /api/backtest 응답 사용 — 경로 회귀 방어선.
    await page.goto('/backtest');

    // empty state 는 나타나면 안 됨
    await expect(page.getByText('백테스팅을 아직 실행하지 않았어요')).toHaveCount(0);

    // 3개 SignalType 라벨이 실데이터에서 모두 나타나는지 확인.
    // 데스크톱 table 과 모바일 card 가 동시에 DOM 에 존재할 수 있으므로 first() 로 제한.
    await expect(page.getByText('대차 급감').first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText('추세 전환').first()).toBeVisible();
    await expect(page.getByText('숏스퀴즈').first()).toBeVisible();

    // 차트 섹션 헤딩 렌더
    await expect(
      page.getByRole('heading', { level: 2, name: '보유기간별 평균 수익률' }),
    ).toBeVisible();
  });
});

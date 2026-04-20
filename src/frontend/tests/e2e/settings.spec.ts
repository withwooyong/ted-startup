import { test, expect } from '@playwright/test';

/**
 * 설정 페이지는 서버 싱글톤(notification_preference id=1) 을 그대로 편집한다.
 * I1~I5 는 **로컬 React state 조작만** 수행하고 저장(PUT)은 누르지 않는다 —
 * 다른 테스트가 가정하는 기본값(min_score=60, 3종 타입 전부 활성)을 보존하기 위함.
 * I6 는 `page.route` 로 PUT 을 인터셉트해 실제 백엔드에 닿지 않게 한 뒤
 * 성공/실패 toast 경로를 각각 검증한다 (싱글톤 mutation 0건).
 */
test.describe('I. 설정 페이지', () => {
  test('I1: /settings 진입 — h1 "알림 설정" + 채널 스위치 4개 렌더', async ({ page }) => {
    await page.goto('/settings');

    await expect(page.getByRole('heading', { level: 1, name: '알림 설정' })).toBeVisible({
      timeout: 10_000,
    });

    // role=switch 4개 (일일 요약 / 긴급 알림 (A등급) / 배치 실패 / 주간 리포트)
    const switches = page.getByRole('switch');
    await expect(switches).toHaveCount(4);
    await expect(page.getByText('일일 요약', { exact: true })).toBeVisible();
    await expect(page.getByText('긴급 알림 (A등급)', { exact: true })).toBeVisible();
  });

  test('I2: 채널 스위치 클릭 → aria-checked 전환', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.getByRole('heading', { level: 1, name: '알림 설정' })).toBeVisible({
      timeout: 10_000,
    });

    const firstSwitch = page.getByRole('switch').first();
    const initial = await firstSwitch.getAttribute('aria-checked');
    await firstSwitch.click();
    const toggled = await firstSwitch.getAttribute('aria-checked');
    expect(toggled).not.toBe(initial);

    // 되돌리기 — 테스트 간 상태 누적 방지(React state 만 영향이지만 습관 유지)
    await firstSwitch.click();
    await expect(firstSwitch).toHaveAttribute('aria-checked', initial ?? 'true');
  });

  test('I3: 시그널 타입 칩 클릭 → aria-pressed 전환', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.getByRole('heading', { level: 1, name: '알림 설정' })).toBeVisible({
      timeout: 10_000,
    });

    const group = page.getByRole('group', { name: '알림 대상 시그널 타입' });
    const rapid = group.getByRole('button', { name: '급감' });

    // 기본값은 3종 전부 active=true → pressed=true 에서 시작
    await expect(rapid).toHaveAttribute('aria-pressed', 'true');
    await rapid.click();
    await expect(rapid).toHaveAttribute('aria-pressed', 'false');
    await rapid.click();
    await expect(rapid).toHaveAttribute('aria-pressed', 'true');
  });

  test('I4: 시그널 타입 전부 해제 → 저장 비활성 + 경고 메시지', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.getByRole('heading', { level: 1, name: '알림 설정' })).toBeVisible({
      timeout: 10_000,
    });

    const group = page.getByRole('group', { name: '알림 대상 시그널 타입' });
    // 3개 전부 해제 (기본값이 전부 활성)
    await group.getByRole('button', { name: '급감' }).click();
    await group.getByRole('button', { name: '추세전환' }).click();
    await group.getByRole('button', { name: '숏스퀴즈' }).click();

    await expect(page.getByText('최소 한 개의 타입을 선택해주세요')).toBeVisible();
    const save = page.getByRole('button', { name: '저장', exact: true });
    await expect(save).toBeDisabled();

    // 복원 — 다음 테스트 영향 최소화
    await group.getByRole('button', { name: '급감' }).click();
    await group.getByRole('button', { name: '추세전환' }).click();
    await group.getByRole('button', { name: '숏스퀴즈' }).click();
  });

  test('I5: 최소 스코어 슬라이더 값 조작 → 숫자 라벨 갱신', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.getByRole('heading', { level: 1, name: '알림 설정' })).toBeVisible({
      timeout: 10_000,
    });

    const slider = page.getByRole('slider', { name: '최소 스코어 (0-100)' });
    // 기본값 60 (pref.minScore) — 라벨 숫자도 동일
    const scoreHeading = page.getByRole('heading', { level: 2, name: '최소 스코어' });
    const scoreCard = scoreHeading.locator('..');
    await expect(scoreCard).toContainText(/\b60\b/);

    // HTML range input 은 키보드로 step 단위 이동(ArrowRight=+step, step=5)
    await slider.focus();
    await slider.press('ArrowLeft');
    await slider.press('ArrowLeft');
    // 60 - 5*2 = 50 기대
    await expect(scoreCard).toContainText(/\b50\b/);
  });

  test('I6-1: 저장 클릭 → PUT 인터셉트(200) + "저장되었습니다" toast + payload 검증', async ({ page }) => {
    // PUT URL(`/api/admin/notifications/preferences`) 만 인터셉트 — GET URL 은
    // `/api/notifications/preferences`(admin 경로 아님) 이므로 이 route 와 매칭되지 않아
    // 초기 로딩은 실제 백엔드로 pass-through 된다.
    await page.route('**/api/admin/notifications/preferences', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          daily_summary_enabled: true,
          urgent_alert_enabled: true,
          batch_failure_enabled: true,
          weekly_report_enabled: true,
          min_score: 60,
          signal_types: ['RAPID_DECLINE', 'TREND_REVERSAL', 'SHORT_SQUEEZE'],
          updated_at: '2026-04-20T09:00:00+09:00',
        }),
      }),
    );

    await page.goto('/settings');
    await expect(page.getByRole('heading', { level: 1, name: '알림 설정' })).toBeVisible({
      timeout: 10_000,
    });

    // waitForRequest + click 을 Promise.all 로 동기화 — toast 가시성 타이밍과
    // 핸들러 콜백 실행 타이밍 사이 race 를 제거.
    const [putRequest] = await Promise.all([
      page.waitForRequest(
        req =>
          req.url().includes('/api/admin/notifications/preferences') && req.method() === 'PUT',
      ),
      page.getByRole('button', { name: '저장', exact: true }).click(),
    ]);

    // form payload 가 PUT body 에 그대로 실렸는지 — "저장 버튼이 진짜 PUT 을 트리거" 증명
    expect(putRequest.postDataJSON()).toMatchObject({
      daily_summary_enabled: true,
      urgent_alert_enabled: true,
      min_score: 60,
      signal_types: expect.arrayContaining([
        'RAPID_DECLINE',
        'TREND_REVERSAL',
        'SHORT_SQUEEZE',
      ]),
    });

    // 성공 toast (role=status 로 렌더, 2500ms 자동 소멸 — hasText 로 다른 status 영역과 분리)
    const successToast = page
      .getByRole('status')
      .filter({ hasText: '저장되었습니다' });
    await expect(successToast).toBeVisible({ timeout: 5_000 });
  });

  test('I6-2: PUT 인터셉트(500) → "서버 오류가 발생했습니다…" toast', async ({ page }) => {
    await page.route('**/api/admin/notifications/preferences', route =>
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Internal Server Error' }),
      }),
    );

    await page.goto('/settings');
    await expect(page.getByRole('heading', { level: 1, name: '알림 설정' })).toBeVisible({
      timeout: 10_000,
    });

    await page.getByRole('button', { name: '저장', exact: true }).click();

    const errorToast = page
      .getByRole('status')
      .filter({ hasText: '서버 오류가 발생했습니다' });
    await expect(errorToast).toBeVisible({ timeout: 5_000 });
  });
});

import { test, expect } from '@playwright/test';

/**
 * 설정 페이지는 서버 싱글톤(notification_preference id=1) 을 그대로 편집한다.
 * I1~I5 는 **로컬 React state 조작만** 수행하고 저장(PUT)은 누르지 않는다 —
 * 다른 테스트가 가정하는 기본값(min_score=60, 3종 타입 전부 활성)을 보존하기 위함.
 * 저장 경로 검증(I6)은 격리 전략(page.route 인터셉트 또는 복원 afterEach) 확정 후 별도 PR.
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
});

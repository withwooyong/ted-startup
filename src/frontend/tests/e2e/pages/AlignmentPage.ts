import type { Page, Locator } from '@playwright/test';

export class AlignmentPage {
  readonly page: Page;
  readonly heading: Locator;
  readonly backLink: Locator;
  readonly minScoreSlider: Locator;
  readonly emptyState: Locator;
  readonly errorBox: Locator;

  constructor(page: Page) {
    this.page = page;
    this.heading = page.getByRole('heading', { level: 1 });
    this.backLink = page.getByRole('link', { name: '← 포트폴리오' });
    this.minScoreSlider = page.getByLabel('최소 스코어');
    this.emptyState = page.getByText(/기간 내 해당 기준.*시그널이 없습니다/);
    this.errorBox = page.getByText(/유효하지 않은 계좌 ID|조회 실패/);
  }

  async goto(accountId: number | string, minScore = 60): Promise<void> {
    await this.page.goto(`/portfolio/${accountId}/alignment`);
    if (minScore !== 60) {
      await this.setMinScore(minScore);
    }
  }

  async setMinScore(value: number): Promise<void> {
    // React controlled input: value setter 를 native 로 호출해야 onChange 가 트리거됨.
    await this.minScoreSlider.evaluate((el, v) => {
      const input = el as HTMLInputElement;
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        'value',
      )?.set;
      setter?.call(input, String(v));
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }, value);
  }
}

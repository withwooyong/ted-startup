import type { Page, Locator } from '@playwright/test';

export class PortfolioPage {
  readonly page: Page;
  readonly accountTabs: Locator;
  readonly metricsSection: Locator;
  readonly holdingsSection: Locator;
  /** Desktop (`>= sm`) 전용 테이블. 모바일 프로필에선 `display: none` 상태라 `toBeVisible()` 사용 금지. */
  readonly holdingsTable: Locator;
  /** 모바일/데스크톱 공통 — 어느 뷰포트에서든 렌더된 보유 종목 컨테이너(섹션) 가시성 검증용. */
  readonly holdingsContainer: Locator;
  readonly emptyHoldings: Locator;
  readonly snapshotButton: Locator;
  /** 라벨이 뷰포트별로 분기됨: 모바일 "모의 sync" / 데스크톱 "KIS 모의 동기화". 실계좌는 "실계좌 sync" / "KIS 실계좌 동기화". */
  readonly kisSyncButton: Locator;
  readonly alignmentLink: Locator;

  constructor(page: Page) {
    this.page = page;
    this.accountTabs = page.getByRole('tablist', { name: '계좌 탭' });
    this.metricsSection = page.getByRole('region', { name: '계좌 지표' });
    this.holdingsSection = page.locator('section[aria-labelledby="holdings-title"]');
    this.holdingsTable = this.holdingsSection.locator('table');
    this.holdingsContainer = this.holdingsSection;
    this.emptyHoldings = this.holdingsSection.getByText('보유 종목이 없습니다.');
    this.snapshotButton = page.getByRole('button', { name: /스냅샷 생성/ });
    this.kisSyncButton = page.getByRole('button', {
      name: /KIS 모의 동기화|모의 sync|KIS 실계좌 동기화|실계좌 sync/,
    });
    this.alignmentLink = page.getByRole('link', { name: '시그널 정합도' });
  }

  async goto(): Promise<void> {
    await this.page.goto('/portfolio');
  }

  accountTab(alias: string): Locator {
    return this.accountTabs.getByRole('tab', { name: new RegExp(alias) });
  }

  async selectAccount(alias: string): Promise<void> {
    await this.accountTab(alias).click();
  }

  metricByLabel(label: string): Locator {
    // Metric 컴포넌트: label div 가 있고, 형제 div 에 value
    return this.metricsSection.locator('div', { hasText: label }).last();
  }

  /**
   * 보유 종목 행. 뷰포트 불문 — 데스크톱은 `<tr data-testid="holding-row">`,
   * 모바일은 `<li data-testid="holding-row">` 로 동일 testid 를 공유한다.
   * `hasText` 로 종목코드 필터링.
   */
  holdingRow(stockCode: string): Locator {
    return this.page.getByTestId('holding-row').filter({ hasText: stockCode });
  }
}

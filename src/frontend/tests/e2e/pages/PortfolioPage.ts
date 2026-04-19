import type { Page, Locator } from '@playwright/test';

export class PortfolioPage {
  readonly page: Page;
  readonly accountTabs: Locator;
  readonly metricsSection: Locator;
  readonly holdingsSection: Locator;
  readonly holdingsTable: Locator;
  readonly emptyHoldings: Locator;
  readonly snapshotButton: Locator;
  readonly kisSyncButton: Locator;
  readonly alignmentLink: Locator;

  constructor(page: Page) {
    this.page = page;
    this.accountTabs = page.getByRole('tablist', { name: '계좌 탭' });
    this.metricsSection = page.getByRole('region', { name: '계좌 지표' });
    this.holdingsSection = page.locator('section[aria-labelledby="holdings-title"]');
    this.holdingsTable = this.holdingsSection.locator('table');
    this.emptyHoldings = this.holdingsSection.getByText('보유 종목이 없습니다.');
    this.snapshotButton = page.getByRole('button', { name: /스냅샷 생성/ });
    this.kisSyncButton = page.getByRole('button', { name: /KIS 모의 동기화/ });
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

  holdingRow(stockCode: string): Locator {
    return this.holdingsTable.locator('tbody tr', { hasText: stockCode });
  }
}

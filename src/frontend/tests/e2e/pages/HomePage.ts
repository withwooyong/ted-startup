import type { Page, Locator } from '@playwright/test';

export class HomePage {
  readonly page: Page;
  readonly nav: Locator;
  readonly portfolioLink: Locator;
  readonly settingsLink: Locator;

  constructor(page: Page) {
    this.page = page;
    this.nav = page.getByRole('navigation', { name: '주 메뉴' });
    this.portfolioLink = this.nav.getByRole('link', { name: '포트폴리오' });
    this.settingsLink = this.nav.getByRole('link', { name: '설정' });
  }

  async goto(): Promise<void> {
    await this.page.goto('/');
  }

  async openPortfolio(): Promise<void> {
    await this.portfolioLink.click();
    await this.page.waitForURL('**/portfolio');
  }

  async openSettings(): Promise<void> {
    await this.settingsLink.click();
    await this.page.waitForURL('**/settings');
  }
}

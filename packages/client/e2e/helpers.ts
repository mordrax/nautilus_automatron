import type { Page } from '@playwright/test'
import { expect } from '@playwright/test'

/**
 * Enables an indicator via the new parameterized Add popover.
 * Uses default params — click Add → pick type → click Add button in form.
 * For custom params, use the lower-level helpers in parameterized-indicators.spec.ts.
 *
 * @param page     Playwright page object
 * @param typeName The indicator type key, e.g. "SMA", "RSI", "ATR", "ZigZag"
 */
export const enableIndicator = async (page: Page, typeName: string): Promise<void> => {
  await page.getByTestId('add-indicator-button').click()
  await page.locator('[data-testid="indicator-type-option"]', { hasText: typeName }).click()
  // The param form appears with defaults — just submit
  await page.getByTestId('param-form-submit').click()
  // Wait for popover to close (form submit hides it)
  await expect(page.getByTestId('param-form-submit')).not.toBeVisible()
}

/**
 * Removes an indicator chip by its displayed label (e.g. "SMA(20)").
 */
export const removeIndicator = async (page: Page, label: string): Promise<void> => {
  const selector = page.getByTestId('indicator-instance-selector')
  const chip = selector.locator('[data-testid="indicator-chip"]', { hasText: label })
  await chip.getByTestId('indicator-chip-remove').click()
}

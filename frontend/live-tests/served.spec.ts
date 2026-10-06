import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test('aplicação real 5128, desktop/mobile, preparação, integrações e temas', async ({ page, request }) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  const leads = await (await request.get('/api/ed/empresas')).json()
  const lead = leads.find((x: { observacoes: string }) => x.observacoes.includes('PILOTO TÉCNICO DE PREPARAÇÃO'))
  expect(lead).toBeTruthy()
  await page.goto(`/empresas/${lead.id}`)
  await page.getByRole('button', { name: 'Preparar prévia', exact: true }).click()
  await expect(page.getByLabel('Tipo de entrega')).toHaveValue('previa')
  await expect(page.getByLabel('Shaders · atmosfera do nicho')).toContainText('papel')
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  await page.screenshot({ path: '../.cache/screenshots/kit-regressao/5128-preparacao-desktop.png' })
  for (const width of [320, 390, 768]) {
    await page.setViewportSize({ width, height: 844 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  }
  await page.setViewportSize({ width: 390, height: 844 })
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  await page.screenshot({ path: '../.cache/screenshots/kit-regressao/5128-preparacao-mobile.png' })
  await page.setViewportSize({ width: 1440, height: 900 })
  for (const theme of ['escuro', 'nebulosa']) {
    await page.goto('/configuracoes/aparencia')
    await page.getByRole('button', { name: theme === 'escuro' ? /^Escuro/ : /^Nebulosa/ }).click()
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  }
  await page.goto('/integracoes')
  await expect(page.getByRole('heading', { name: 'Firecrawl', exact: true })).toBeVisible()
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  await page.screenshot({ path: '../.cache/screenshots/kit-regressao/5128-integracoes.png' })
  for (const path of ['/', '/nova-busca', '/campanhas']) {
    await page.goto(path)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  }
  expect(errors).toEqual([])
})

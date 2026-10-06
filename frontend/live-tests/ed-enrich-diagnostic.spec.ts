import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test('5128: diagnóstico real existente e recuperação sem alterar o lead', async ({ page, request }) => {
  const id = 'c838cefefed541be9aba0b286f924f8b'
  const before = await (await request.get(`/api/ed/empresas/${id}`)).json()
  const research = await (await request.get(`/api/ed/empresas/${id}/pesquisa`)).json()
  expect(research.diagnostico_atual.estado).toBe('permitida')
  await page.goto(`/empresas/${id}`)
  await page.getByRole('button', { name: 'Pesquisa do site', exact: true }).click()
  await expect(page.getByText('Nenhuma página lida. Pesquisa não concluída;', { exact: false })).toBeVisible()
  expect(before.site).toBe('')
  expect(before.fonte_busca_url).toBe('http://google.com.br')
  expect(before.historico_site.some((h: {valor_anterior:string}) => h.valor_anterior === 'http://google.com.br')).toBeTruthy()
  await expect(page.getByText('Sem site confirmado · associação pendente', { exact: true })).toBeVisible()
  await page.getByText(/^Histórico da URL e da associação/).click()
  await expect(page.getByText('Nenhum site substituto', { exact: false })).toBeVisible()
  await expect(page.getByText('A política atual permite a URL inicial', { exact: false })).toBeVisible()
  await expect(page.locator('option[value="firecrawl"]')).toBeDisabled()
  await page.getByText('Regras verificadas agora', { exact: true }).click()
  await expect(page.getByText('EdCRM/0.2', { exact: false })).toBeVisible()
  await page.screenshot({ path: '../.cache/screenshots/kit-regressao/5128-enriquecimento-diagnostico-desktop.png', fullPage: true })
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 844 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  }
  await page.setViewportSize({ width: 390, height: 844 })
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  await page.screenshot({ path: '../.cache/screenshots/kit-regressao/5128-enriquecimento-diagnostico-mobile.png', fullPage: true })
  await page.getByRole('button', { name: 'Revisar site / adicionar informações', exact: true }).click()
  await expect(page.getByLabel('Site', { exact: true })).toHaveValue(before.site)
  await page.getByRole('button', { name: 'Voltar à ficha', exact: true }).click()
  await page.getByRole('button', { name: 'Pesquisa do site', exact: true }).click()
  await page.getByRole('button', { name: 'Enviar materiais manualmente', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Enviar imagem', exact: true })).toBeVisible()
  expect(await (await request.get(`/api/ed/empresas/${id}`)).json()).toEqual(before)
})

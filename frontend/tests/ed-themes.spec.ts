import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs'
import path from 'node:path'

test('três temas, prévias, persistência, pausa, aba oculta e movimento reduzido', async ({ page, context }) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  const fixture = await (await page.request.post('/api/ed/empresas', { data: { nome: 'Empresa fictícia — verificação de temas', demonstracao: true } })).json()
  await page.goto('/')
  await page.setViewportSize({ width: 1440, height: 1050 })
  fs.mkdirSync(path.resolve('../.cache/screenshots/temas'), { recursive: true })
  for (const [theme, label] of [['claro', 'Claro'], ['escuro', 'Escuro'], ['nebulosa', 'Nebulosa']]) {
    await page.goto('/configuracoes/aparencia')
    await page.getByRole('button', { name: new RegExp('^' + label) }).click()
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
    await expect(page.getByRole('button', { name: new RegExp(`^${label}`), exact: true })).toHaveAttribute('aria-pressed', 'true')
    await page.screenshot({ path: `../.cache/screenshots/temas/${theme}-desktop.png` })
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
    for (const width of [320, 390, 768]) {
      await page.setViewportSize({ width, height: 844 })
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
      await expect(page.getByRole('heading', { name: 'Aparência', exact: true })).toBeVisible()
      if (width === 390) await page.screenshot({ path: `../.cache/screenshots/temas/${theme}-mobile.png`, fullPage: true })
    }
    await page.setViewportSize({ width: 1440, height: 1050 })
    for (const route of ['/empresas/nova', '/nova-busca', '/campanhas', '/integracoes']) {
      await page.goto(route)
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
    }
    await page.goto(`/empresas/${fixture.id}`)
    await expect(page.getByRole('heading', { name: 'Empresa fictícia — verificação de temas' })).toBeVisible()
    for (const section of ['Ficha da empresa', 'Materiais', 'Pesquisa do site', 'Documento e exportação', 'Prévia e versões']) {
      await page.getByRole('button', { name: section, exact: true }).click()
      await expect(page.locator('.ed-loading')).toHaveCount(0)
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
    }
    await page.goto('/')
  }
  const cloud = page.locator('.ed-cloud').first()
  const transform = await cloud.evaluate(e => getComputedStyle(e).transform)
  await expect.poll(() => cloud.evaluate(e => getComputedStyle(e).transform)).not.toBe(transform)
  await page.goto('/configuracoes/aparencia')
  await page.getByRole('button', { name: 'Pausar movimento', exact: true }).click()
  expect(await cloud.evaluate(e=>e.getAnimations().length)).toBe(0)
  await page.reload()
  await expect(page.getByRole('button', { name: 'Retomar movimento', exact: true })).toBeVisible()
  expect(await cloud.evaluate(e=>e.getAnimations().length)).toBe(0)
  const other = await context.newPage()
  await other.goto('/')
  await expect(other.locator('html')).toHaveAttribute('data-theme', 'nebulosa')
  await other.close()
  await page.getByRole('button', { name: 'Retomar movimento', exact: true }).click()
  await expect.poll(()=>cloud.evaluate(e=>e.getAnimations().length)).toBe(1)
  // Emulação da condição de visibilidade no perfil isolado de teste.
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, value: true })
    document.dispatchEvent(new Event('visibilitychange'))
  })
  expect(await cloud.evaluate(e=>e.getAnimations().length)).toBe(0)
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, value: false })
    document.dispatchEvent(new Event('visibilitychange'))
  })
  await expect.poll(()=>cloud.evaluate(e=>e.getAnimations().length)).toBe(1)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await expect(cloud).toHaveCSS('animation-name', 'none')
  expect(await cloud.evaluate(e=>e.getAnimations().length)).toBe(0)
  await expect(page.getByText('Movimento reduzido · universo estático')).toBeVisible()
  expect(errors).toEqual([])
})

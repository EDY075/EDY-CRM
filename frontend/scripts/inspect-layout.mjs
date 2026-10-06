import { chromium } from '@playwright/test'
const browser = await chromium.launch({ channel: 'chrome' })
const page = await browser.newPage({ viewport: { width: 320, height: 844 } })
await page.goto('http://127.0.0.1:5128')
await page.getByRole('heading', { name: 'Suas próximas oportunidades.' }).waitFor()
console.log(await page.evaluate(() => ({ width: innerWidth, document: document.documentElement.scrollWidth,
  overflow: [...document.querySelectorAll('*')].filter(el => el.getBoundingClientRect().right > innerWidth + 1 && getComputedStyle(el).position !== 'absolute').map(el => ({
    tag: el.tagName, class: el.className, right: Math.round(el.getBoundingClientRect().right), width: Math.round(el.getBoundingClientRect().width),
  })).slice(0, 30) })))
await browser.close()

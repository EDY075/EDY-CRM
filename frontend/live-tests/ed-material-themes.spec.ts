import {test,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import path from 'node:path'

test('água, fumaça e universo: leitura, pausa, toque, teclado e persistência',async({page})=>{
 test.setTimeout(90000)
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message))
 for(const [theme,label] of [['claro','Claro'],['escuro','Escuro'],['nebulosa','Nebulosa']]){
  await page.goto('/configuracoes/aparencia');await page.getByRole('button',{name:new RegExp('^'+label)}).click();await page.getByRole('button',{name:'Equilibrado',exact:true}).click()
  if(await page.getByRole('button',{name:'Retomar movimento',exact:true}).count())await page.getByRole('button',{name:'Retomar movimento',exact:true}).click()
  await page.goto('/crm/dashboard');await expect(page.getByRole('heading',{name:'Visão do trabalho',exact:true})).toBeVisible();await expect(page.locator('.ed-loading')).toHaveCount(0);const image=page.locator('.ed-universe-image');await image.evaluate(async e=>{await(e as HTMLImageElement).decode()})
  for(const [width,height] of [[1440,900],[390,844],[320,844],[768,900]]){
   await page.setViewportSize({width,height});await page.evaluate(()=>window.scrollTo(0,0));expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()
   if(width===1440||width===390)await page.screenshot({path:path.resolve(`../docs/screenshots/redesign/tema-${theme}-${width===1440?'desktop':'mobile'}.jpg`),type:'jpeg',quality:88,fullPage:width===390})
  }
  const pause=theme==='nebulosa'?'Pausar universo':'Pausar fundo',resume=theme==='nebulosa'?'Retomar universo':'Retomar fundo'
  await page.getByRole('button',{name:pause,exact:true}).click();await expect.poll(()=>image.evaluate(e=>e.getAnimations().length)).toBe(0)
  const transform=await image.evaluate(e=>getComputedStyle(e).transform);await page.waitForTimeout(250);expect(await image.evaluate(e=>getComputedStyle(e).transform)).toBe(transform)
  await page.reload();await expect(page.locator('html')).toHaveAttribute('data-theme',theme);await expect(page.getByRole('button',{name:resume,exact:true})).toBeVisible();await page.getByRole('button',{name:resume,exact:true}).click()
  await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))});await expect.poll(()=>image.evaluate(e=>e.getAnimations().length)).toBe(0)
  await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'))});await expect.poll(()=>image.evaluate(e=>e.getAnimations().length)).toBe(1)
  await page.emulateMedia({reducedMotion:'reduce'});await expect.poll(()=>image.evaluate(e=>e.getAnimations().length)).toBe(0)
  await page.keyboard.press('Tab');expect(await page.evaluate(()=>document.activeElement===document.body)).toBeFalsy()
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);await page.emulateMedia({reducedMotion:'no-preference'})
 }
 expect(errors).toEqual([])
})

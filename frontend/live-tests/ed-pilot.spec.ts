import {test,expect} from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import AxeBuilder from '@axe-core/playwright'

test('PÃO: quatro layouts estruturais e composição existentes, sem salvar mudanças',async({page,request})=>{
 const lead='bd0b8b1d78824672a8c80bce328ec215', endpoint='/api/ed/empresas/'+lead+'/composicao'
 const before=await (await request.get(endpoint)).json()
 await page.goto('/empresas/'+lead);await page.getByRole('button',{name:'Montar composição',exact:true}).click()
 const canvases=page.locator('.ed-alternative-canvas .lp-section');await expect(canvases).toHaveCount(4)
 const layouts=await canvases.evaluateAll(es=>es.map(e=>e.getAttribute('data-layout')))
 expect(layouts).toEqual(['editorial','imersiva','mosaico','compacta'])
 const structures=await canvases.evaluateAll(es=>es.map(e=>Array.from(e.children).map(c=>c.className).join('|')))
 // Editorial/imersiva compartilham DOM, mas usam posições e overlays distintos.
 expect(new Set(structures).size).toBe(3)
 for(const mode of ['desktop','mobile']){
  if(mode==='mobile')await page.getByRole('button',{name:'Desktop',exact:true}).click()
  await page.locator('.ed-alternative-grid').screenshot({path:path.resolve('../docs/screenshots/redesign/pao-quatro-opcoes-'+mode+'.jpg'),type:'jpeg',quality:85})
 }
 await page.getByRole('button',{name:'Ver composição completa',exact:true}).click()
 await expect(page.getByLabel('Composição completa').locator('.lp-section')).toHaveCount(before.secoes.length)
 expect(await (await request.get(endpoint)).json()).toEqual(before)
 fs.writeFileSync(path.resolve('../examples/redesign-piloto/alternativas.json'),JSON.stringify({origem:'Templates locais renderizados na aplicação real; não quatro gerações independentes de IA',layouts,estruturas:structures,secoes:before.secoes.length,revisao:before.revisao,escolhas_preservadas:true},null,2))
})

test('piloto real e ZIP extraído: CTA, teclado, celular e movimento reduzido',async({browser})=>{
 const context=await browser.newContext({reducedMotion:'reduce',viewport:{width:1440,height:900}})
 const page=await context.newPage(), failures:string[]=[],errors:string[]=[]
 page.on('response',r=>{if(r.status()>=400)failures.push(r.url()+':'+r.status())})
 page.on('pageerror',e=>errors.push(e.message))
 const proof=[]
 for(const port of [5131,5180]){
  await page.setViewportSize({width:1440,height:900});await page.goto(`http://127.0.0.1:${port}/`)
  await expect(page.getByRole('heading',{level:1})).toContainText('PÃO')
  for(const a of await page.locator('a[href^="#"]').all()){
   const href=await a.getAttribute('href');expect(await page.locator(href!).count()).toBe(1)
  }
  const tel=await page.locator('a[href^="tel:"]').all();expect(tel.length).toBeGreaterThanOrEqual(2)
  for(const link of tel)expect(await link.getAttribute('href')).toBe('tel:+551182831144')
  // Não aciona telefone, site de terceiros ou envio. Apenas confere o destino.
  expect(await page.locator('a[href^="https:"]').getAttribute('href')).toBe('https://padariaartesanal.com.br/')
  await page.keyboard.press('Tab');await expect(page.getByRole('link',{name:'Pular para o conteúdo'})).toBeFocused()
  await page.keyboard.press('Enter');expect(await page.evaluate(()=>document.activeElement?.id)).toBe('conteudo')
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  const menu=page.locator('.mobile-menu'),summary=menu.locator('summary');await summary.click();await expect(menu).toHaveAttribute('open','')
  await page.keyboard.press('Escape');await expect(menu).not.toHaveAttribute('open','');await expect(summary).toBeFocused()
  const moving=await page.evaluate(()=>document.getAnimations().filter(a=>a.playState==='running'&&(a.effect?.getTiming().iterations===Infinity)).length)
  expect(moving).toBe(0)
  await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.resolve('../docs/screenshots/redesign/pao-entrega-mobile.jpg'),fullPage:true,type:'jpeg',quality:85})
  await page.setViewportSize({width:1440,height:900});await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.resolve('../docs/screenshots/redesign/pao-entrega-desktop.jpg'),fullPage:true,type:'jpeg',quality:85})
  proof.push({porta:port,ancoras:true,telefone:true,teclado:true,menu_mobile:true,movimento_reduzido:true,axe:0})
 }
 expect(failures).toEqual([]);expect(errors).toEqual([])
 fs.writeFileSync(path.resolve('../examples/redesign-piloto/navegacao.json'),JSON.stringify({observacao:'Chrome real, página gerada e ZIP extraído; nenhum contato ou publicação',validacoes:proof,erros:errors,erros_http:failures},null,2))
 await context.close()
})

import {test,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs'
const company='bd0b8b1d78824672a8c80bce328ec215'
const shots='../.cache/screenshots/kit-regressao'
test('5128 real: temas, quatro aberturas, outra seção, estúdio, vínculo e diagnóstico',async({page,request})=>{
 fs.mkdirSync(shots,{recursive:true});const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message))
 const before=await(await request.get(`/api/ed/empresas/${company}`)).json()
 await page.goto(`/empresas/${company}`)
 for(const [id,name] of [['claro','Claro'],['escuro','Escuro'],['nebulosa','Nebulosa']]){
  await page.goto('/configuracoes/aparencia');await page.getByRole('button',{name:new RegExp('^'+name)}).click();await page.goto(`/empresas/${company}`)
  await expect(page.locator('html')).toHaveAttribute('data-theme',id)
  await page.screenshot({path:`${shots}/crm-${id}-desktop.png`})
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:`${shots}/crm-${id}-mobile.png`})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
  await page.setViewportSize({width:1440,height:900})
 }
 await page.getByRole('button',{name:'Montar composição',exact:true}).click()
 await expect(page.locator('.ed-alternative')).toHaveCount(4)
 expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
 await page.getByRole('button',{name:'Ampliar A',exact:true}).click();await page.screenshot({path:`${shots}/quatro-aberturas-desktop.png`})
 await page.getByRole('button',{name:'Fechar ampliação',exact:true}).click();await page.getByLabel('Seção em edição').selectOption('informacoes')
 await expect(page.locator('.ed-alternative')).toHaveCount(4);await page.getByRole('button',{name:'Ampliar C',exact:true}).click();await page.screenshot({path:`${shots}/quatro-informacoes-desktop.png`})
 await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Desktop',exact:true}).click()
 for(const width of [320,390,768]){await page.setViewportSize({width,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()}
 await page.setViewportSize({width:390,height:844});expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);await page.screenshot({path:`${shots}/composicao-mobile.png`})
 await page.getByRole('button',{name:'Estúdio de imagens',exact:true}).click();await expect(page.getByText(/1600 × 1200/)).toBeVisible();expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);await page.screenshot({path:`${shots}/imagens-mobile.png`})
 await page.getByRole('button',{name:'Construir prévia',exact:true}).click();await expect(page.getByText(/model is not supported/).first()).toBeVisible();expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
 const after=await(await request.get(`/api/ed/empresas/${company}`)).json();expect(after).toEqual(before);expect(errors).toEqual([])
})
test('prévia separada real: desktop, celular, links, teclado, pausa, movimento reduzido e recursos',async({page,request})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));const failed:string[]=[];page.on('response',r=>{if(r.status()>=400)failed.push(r.url())})
 const lead=await(await request.get(`/api/ed/empresas/${company}`)).json()
 const previewUrl=lead.previas.find((p:{construcao_id:string})=>p.construcao_id==='2c20ae8c4656453e9144972056a53995')?.url
 expect(previewUrl).toMatch(/^http:\/\/127\.0\.0\.1:\d+\/$/)
 await page.goto(previewUrl)
 await expect(page.getByRole('heading',{name:'PÃO, perto de você.',exact:true})).toBeVisible()
 await expect(page.getByText('Ilustração de demonstração · não representa produtos ou instalações reais.')).toBeVisible()
 await page.screenshot({path:`${shots}/previa-desktop.png`});expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
 await page.keyboard.press('Tab');await expect(page.getByRole('link',{name:'Ir para o conteúdo',exact:true})).toBeFocused()
 await page.keyboard.press('Enter');await expect(page).toHaveURL(/#pagina$/)
 await page.getByRole('button',{name:'Pausar movimento',exact:true}).click();await expect(page.locator('body')).toHaveClass(/is-motion-paused/)
 await page.getByRole('link',{name:'Planejar minha visita ↗',exact:true}).click();await expect(page).toHaveURL(/#contato$/)
 await expect(page.getByRole('link',{name:'(11) 8283-1144',exact:true})).toHaveAttribute('href','tel:1182831144')
 for(const width of [320,390,768]){await page.setViewportSize({width,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])}
 await page.setViewportSize({width:390,height:844});await page.goto(previewUrl);await page.screenshot({path:`${shots}/previa-mobile.png`,fullPage:true})
 await page.emulateMedia({reducedMotion:'reduce'});await expect(page.locator('h1')).toHaveCSS('animation-name','none')
 expect(errors).toEqual([]);expect(failed).toEqual([])
 const timing=await page.evaluate(()=>({recursos:performance.getEntriesByType('resource').length,elementos:document.querySelectorAll('*').length,imagens:Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0),navegacao:performance.getEntriesByType('navigation').map(n=>({duracao:n.duration}))}));fs.writeFileSync('../examples/mestre-pao/navegador-template.json',JSON.stringify(timing,null,2))
})

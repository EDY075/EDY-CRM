import {test,expect} from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import AxeBuilder from '@axe-core/playwright'

const shots=path.resolve('../docs/screenshots/redesign')
test('15 telas reais, desktop e celular, sem alterar dados comerciais',async({page})=>{
 test.setTimeout(120000);fs.mkdirSync(shots,{recursive:true})
 await page.goto('/configuracoes/aparencia');await page.getByRole('button',{name:/^Nebulosa/}).click();await page.getByRole('button',{name:'Equilibrado',exact:true}).click()
 const screens:[string,string,string?][]=[['01-rotinas','/assistente','Rotinas'],['02-comando','/assistente'],['03-execucoes','/assistente','Execuções'],['04-visao','/crm/dashboard'],['05-funil','/crm/funil'],['06-tarefas','/crm/tarefas'],['07-listas','/crm/listas'],['08-importacao','/crm/csv'],['09-empresas','/leads'],['10-pesquisa','/nova-busca'],['11-historico','/campanhas'],['12-biblioteca','/biblioteca/contexto'],['13-geral','/configuracoes/geral'],['14-aparencia','/configuracoes/aparencia'],['15-conexoes','/configuracoes/conexoes']]
 const evidence=[]
 for(const [name,route,tab] of screens){
  await page.setViewportSize({width:1440,height:900});await page.goto(route);await expect(page.getByRole('heading',{level:1})).toBeVisible()
  if(tab)await page.getByRole('button',{name:new RegExp('^'+tab)}).click()
  await expect(page.locator('.ed-loading')).toHaveCount(0);await expect(page.getByText(/^Carregando execução/)).toHaveCount(0);await page.locator('.ed-universe-image').evaluate(async e=>{await (e as HTMLImageElement).decode()});await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(shots,'depois-'+name+'-desktop.jpg'),type:'jpeg',quality:85})
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()
  await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(shots,'depois-'+name+'-mobile.jpg'),type:'jpeg',quality:85,fullPage:true})
  evidence.push({name,route,desktop:[1440,900],mobile:[390,844]})
 }
 fs.writeFileSync(path.join(shots,'capturas.json'),JSON.stringify(evidence,null,2))
 for(const route of ['/','/leads','/previas','/configuracoes/conexoes']){await page.goto(route);await expect(page.getByRole('heading',{level:1})).toBeVisible();await expect(page.locator('.ed-loading')).toHaveCount(0);expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])}
})

test('vídeo real do fundo através do vidro durante edição e rolagem',async({browser})=>{
 const context=await browser.newContext({viewport:{width:1440,height:900},recordVideo:{dir:path.resolve('../.cache/video-redesign'),size:{width:1440,height:900}},reducedMotion:'no-preference'})
 const page=await context.newPage();await page.goto('http://127.0.0.1:5128/configuracoes/aparencia')
 await page.getByRole('button',{name:/^Nebulosa/}).click();await page.getByRole('button',{name:'Equilibrado',exact:true}).click()
 if(await page.getByRole('button',{name:'Retomar movimento',exact:true}).count())await page.getByRole('button',{name:'Retomar movimento',exact:true}).click()
 await page.goto('http://127.0.0.1:5128/');await page.getByLabel('Seu comando').fill('Prepare uma prévia editorial da PÃO. — texto não executado nesta gravação')
 const cloud=page.locator('.ed-cloud').first(),start=await cloud.evaluate(e=>getComputedStyle(e).transform)
 const sample=await page.evaluate(()=>new Promise<{frames:number;p95_ms:number}>(resolve=>{const samples:number[]=[];let last=performance.now();const beginning=last;function frame(now:number){samples.push(now-last);last=now;if(now-beginning<10000)requestAnimationFrame(frame);else{samples.sort((a,b)=>a-b);resolve({frames:samples.length,p95_ms:samples[Math.floor(samples.length*.95)]})}}requestAnimationFrame(frame)}))
 expect(await cloud.evaluate(e=>getComputedStyle(e).transform)).not.toBe(start)
 await page.keyboard.press('Tab');await page.mouse.wheel(0,450);await page.screenshot({path:path.join(shots,'movimento-frame.jpg'),type:'jpeg',quality:85})
 fs.writeFileSync(path.join(shots,'desempenho-movimento.json'),JSON.stringify({origem:'Chrome real /5128, medição local durante digitação; não é benchmark universal',...sample},null,2))
 const video=page.video()!;await context.close();await video.saveAs(path.resolve('../docs/screenshots/redesign/universo-em-uso.webm'))
})

import {test,expect} from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const out=path.resolve('../docs/screenshots/redesign')
test('fluidez comparada, entrada, rolagem e controles do universo',async({browser})=>{
 test.setTimeout(150000);const results=[]
 for(const [name,url] of [['referencia','http://127.0.0.1:5164/dashboard-glass.html'],...['claro','escuro','nebulosa'].map(t=>['crm-'+t,'http://127.0.0.1:5128/crm/dashboard'])]){
  for(const [device,width,height] of [['desktop',1440,900],['mobile',390,844]] as const){
   const ctx=await browser.newContext({viewport:{width,height},reducedMotion:'no-preference'}),page=await ctx.newPage()
   if(name.startsWith('crm')){
    await page.goto('http://127.0.0.1:5128/configuracoes/aparencia');await page.getByRole('button',{name:new RegExp('^'+({claro:'Claro',escuro:'Escuro',nebulosa:'Nebulosa'} as Record<string,string>)[name.slice(4)])}).click();await page.getByRole('button',{name:'Equilibrado',exact:true}).click()
    if(await page.getByRole('button',{name:'Retomar movimento',exact:true}).count())await page.getByRole('button',{name:'Retomar movimento',exact:true}).click()
   }
   await page.goto(url);await expect(name.startsWith('crm')?page.locator('h1'):page.locator('.stat').first()).toBeVisible();await page.evaluate(()=>document.fonts.ready)
   if(name.startsWith('crm'))await page.locator('.ed-universe-image').evaluate(async e=>{await (e as HTMLImageElement).decode()});await page.waitForTimeout(300)
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()
   await page.screenshot({path:path.join(out,`${name}-glass-${device}.jpg`),type:'jpeg',quality:90,fullPage:device==='mobile'})
   const cdp=await ctx.newCDPSession(page);await cdp.send('Emulation.setCPUThrottlingRate',{rate:4})
   const sample=page.evaluate(()=>new Promise(resolve=>{
    const frames:number[]=[],tasks:number[]=[];let last=performance.now();const beginning=last
    const observer=new PerformanceObserver(list=>tasks.push(...list.getEntries().map(e=>e.duration)));observer.observe({type:'longtask',buffered:false})
    function frame(now:number){frames.push(now-last);last=now;if(now-beginning<8000)requestAnimationFrame(frame);else{
     observer.disconnect();frames.sort((a,b)=>a-b);resolve({frames:frames.length,frame_p95_ms:frames[Math.floor(frames.length*.95)],frames_acima_33ms:frames.filter(n=>n>33).length,long_tasks:tasks.length,long_task_max_ms:Math.max(0,...tasks),dom_nodes:document.querySelectorAll('*').length})
    }}requestAnimationFrame(frame)
   }))
   const scroll=[];for(let i=0;i<4;i++){const start=performance.now();await page.mouse.wheel(0,300);scroll.push(performance.now()-start);await page.waitForTimeout(200)}
   const metrics=await sample
   const resources=await page.evaluate(()=>performance.getEntriesByType('resource').map(r=>({nome:new URL(r.name).pathname,transferencia:(r as PerformanceResourceTiming).transferSize,tipo:(r as PerformanceResourceTiming).initiatorType})))
   results.push({name,device,cpu_throttle:4,...metrics as object,scroll_dispatch_ms:scroll,resources})
   if(name.startsWith('crm')){
    const image=page.locator('.ed-universe-image');await expect.poll(()=>image.evaluate(e=>e.getAnimations().length)).toBe(1)
    await page.getByRole('button',{name:name==='crm-nebulosa'?'Pausar universo':'Pausar fundo',exact:true}).click();await expect.poll(()=>image.evaluate(e=>e.getAnimations().length)).toBe(0)
    const before=await image.evaluate(e=>getComputedStyle(e).transform);await page.waitForTimeout(300);expect(await image.evaluate(e=>getComputedStyle(e).transform)).toBe(before)
    await page.reload();await expect(page.getByRole('button',{name:name==='crm-nebulosa'?'Retomar universo':'Retomar fundo',exact:true})).toBeVisible()
    await page.getByRole('button',{name:name==='crm-nebulosa'?'Retomar universo':'Retomar fundo',exact:true}).click();await page.emulateMedia({reducedMotion:'reduce'});await expect.poll(()=>image.evaluate(e=>e.getAnimations().length)).toBe(0)
   }
   await ctx.close()
  }
 }
 const ctx=await browser.newContext({viewport:{width:1440,height:900}}),page=await ctx.newPage();await page.goto('http://127.0.0.1:5128/');const input=page.getByLabel('Seu comando');await expect(input).toBeVisible()
 const times=[];for(const text of ['Preparar uma prévia','Preparar uma prévia para PÃO','Texto de teste — sem executar']){const start=performance.now();await input.fill(text);await expect(input).toHaveValue(text);times.push(performance.now()-start)}
 await ctx.close();fs.writeFileSync(path.join(out,'desempenho-glass.json'),JSON.stringify({ambiente:'Chrome local; CPU 4x artificial nos quadros; intervalos RAF e long tasks, não prova de FPS de GPU nem benchmark universal',medicoes:results,preenchimento_e_confirmacao_ms:times},null,2))
})

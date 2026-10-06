// Worker de produto. Página externa não recebe bridge/token ou APIs administrativas.
import {createRequire} from 'node:module'
import fs from 'node:fs/promises'
import path from 'node:path'
const require=createRequire(new URL('../frontend/package.json',import.meta.url))
const {chromium}=require('playwright')
const [url,out]=process.argv.slice(2)
let browser
try{
 browser=await chromium.launch({channel:'chrome',headless:true,args:['--disable-background-networking','--force-webrtc-ip-handling-policy=disable_non_proxied_udp']})
 const context=await browser.newContext({serviceWorkers:'block',acceptDownloads:false,permissions:[],userAgent:'EdCRM/0.2 (public website research; local human review)',reducedMotion:'reduce'})
 await context.routeWebSocket('**/*',ws=>ws.close())
 await context.route('**/*',async route=>{
  const req=route.request()
  if(req.method()!=='GET'||!/^https?:\/\//.test(req.url())||['xhr','fetch','websocket','eventsource','manifest','other'].includes(req.resourceType()))return route.abort()
  if(req.isNavigationRequest()&&req.frame().parentFrame())return route.abort()
  try{
   const r=await fetch(process.env.EDY_VISUAL_BRIDGE,{method:'POST',headers:{Authorization:'Bearer '+process.env.EDY_VISUAL_TOKEN,'Content-Type':'application/json'},body:JSON.stringify({url:req.url()}),signal:AbortSignal.timeout(18000)})
   const data=await r.json()
   if(!r.ok||!data.body)return route.abort()
   const headers={'content-type':data.mime,'access-control-allow-origin':'*','referrer-policy':'no-referrer'}
   if(req.resourceType()==='document')headers['content-security-policy']="default-src 'none'; script-src http: https: 'unsafe-inline' 'unsafe-eval'; style-src http: https: 'unsafe-inline'; img-src http: https: data: blob:; font-src http: https: data:; connect-src 'none'; worker-src 'none'; frame-src 'none'; object-src 'none'; form-action 'none'; base-uri 'self'"
   await route.fulfill({status:200,headers,body:Buffer.from(data.body,'base64')})
  }catch{await route.abort()}
 })
 const page=await context.newPage();page.on('dialog',d=>d.dismiss())
 const records=[]
 for(const [label,width,height] of [['desktop',1440,900],['mobile',390,844]]){
  await page.setViewportSize({width,height})
  await page.goto(url,{waitUntil:'load',timeout:30000})
  await page.locator('h1,h2').first().waitFor({state:'visible',timeout:8000})
  await page.evaluate(()=>document.fonts.ready)
  // Somente medidas de DOM/cascata e pequenas rolagens; não clicar CTA, comprar ou preencher.
  const metrics=await page.evaluate(()=>({titulo:document.title.slice(0,180),titulos:[...document.querySelectorAll('h1,h2')].slice(0,25).map(e=>e.textContent.trim().slice(0,180)),
   texto:document.body.innerText.trim().slice(0,200),overflow:document.documentElement.scrollWidth>innerWidth,
   tipografia:[...document.querySelectorAll('h1,h2,p,a')].slice(0,40).map(e=>{const s=getComputedStyle(e);return {elemento:e.tagName,font:s.fontFamily,tamanho:s.fontSize,peso:s.fontWeight,cor:s.color}}),
   imagens:[...document.images].slice(0,30).map(e=>({origem:e.currentSrc||e.src,alt:e.alt,largura:e.naturalWidth,altura:e.naturalHeight,recorte:getComputedStyle(e).objectFit,posicao:getComputedStyle(e).objectPosition})),
   controles:[...document.querySelectorAll('button[aria-expanded],summary')].slice(0,15).map(e=>({texto:e.textContent.trim().slice(0,120),expandido:e.getAttribute('aria-expanded')})),
   movimento:{css:[...document.querySelectorAll('h1,h2,main,section')].slice(0,20).map(e=>getComputedStyle(e).animationName),preferencia:'reduce'},
   altura:document.documentElement.scrollHeight,secoes:[...document.querySelectorAll('section')].slice(0,30).map(e=>({id:e.id,classe:e.className.slice(0,180)}))}))
  if(metrics.texto.length<80||!metrics.titulos.length)throw Error('Sem conteúdo renderizado suficiente')
  await page.screenshot({path:path.join(out,label+'.jpg'),type:'jpeg',quality:82})
  await page.mouse.wheel(0,650)
  await page.screenshot({path:path.join(out,label+'-scroll.jpg'),type:'jpeg',quality:80})
  // Expansão limitada a menu/FAQ declarados, sem formulários ou comunicação remota.
  const control=page.locator('button[aria-expanded=false]').filter({hasText:/^(menu|perguntas|faq)$/i}).first()
  let interaction={tipo:'rolagem',observado:true}
  if(await control.count()){
   await control.click({timeout:2000});interaction={tipo:'expansao_menu_faq',observado:await control.getAttribute('aria-expanded')==='true'}
  }
  records.push({viewport:label,width,height,...metrics,interacao:interaction})
 }
 await fs.writeFile(path.join(out,'resultado.json'),JSON.stringify({schema:1,url,fonte:'chrome_local_isolado',viewports:records,observacoes:['Screenshot é referência de composição; não transfere direitos dos assets.','CSS computado e interação observada não comprovam biblioteca ou backend.','XHR/Fetch, frames, workers e WebSockets bloqueados; algumas páginas podem ficar parciais.']}))
}catch{
 await fs.writeFile(path.join(out,'resultado.json'),JSON.stringify({erro:'Navegação/renderização incompleta; dados anteriores preservados.'}));process.exitCode=1
}finally{if(browser)await browser.close()}

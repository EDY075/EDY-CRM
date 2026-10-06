// Captura local isolada, sem autenticação do CRM ou rede externa.
import {chromium} from '../frontend/node_modules/@playwright/test/index.mjs'
import path from 'node:path'
const [url,out]=process.argv.slice(2),parsed=new URL(url)
if(parsed.hostname!=='127.0.0.1'||parsed.protocol!=='http:'||!out)throw Error('Prévia local necessária')
const browser=await chromium.launch({channel:'chrome',headless:true})
try{
 const context=await browser.newContext({viewport:{width:1280,height:800},reducedMotion:'reduce'})
 await context.route('**/*',r=>{const u=new URL(r.request().url());return ['data:','blob:'].includes(u.protocol)||u.origin===parsed.origin?r.continue():r.abort()})
 const page=await context.newPage();await page.goto(url,{waitUntil:'networkidle',timeout:10000})
 await page.screenshot({path:path.resolve(out),type:'jpeg',quality:75})
}finally{await browser.close()}

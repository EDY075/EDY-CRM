import {test,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

// Artefato real já gerado, extraído e servido à parte. Nenhuma inferência ou escrita no lead.
test('ZIP Codex reproduzido fora do workspace: renderização e recursos relativos',async({page,request})=>{
 const failed:string[]=[];page.on('response',r=>{if(r.status()>=400)failed.push(r.url())})
 await page.goto('http://127.0.0.1:5180/')
 await expect(page.getByRole('heading',{name:'PÃO, perto de você.',exact:true})).toBeVisible()
 await expect(page.getByRole('img')).toHaveAttribute('alt',/não representa produtos reais/)
 expect(await page.evaluate(()=>Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0))).toBeTruthy()
 expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
 const proof=await(await request.get('http://127.0.0.1:5180/contexto.md')).text()
 expect(proof).toContain('EDY_CONTEXTO_PAO_KIT_20261005')
 await page.setViewportSize({width:390,height:844})
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()
 await page.getByRole('link',{name:/Planejar minha visita/}).click()
 await expect(page.locator('#informacoes')).toBeInViewport()
 await expect(page.getByRole('link',{name:/Ligar para/})).toHaveAttribute('href','tel:+551182831144')
 expect(failed).toEqual([])
})

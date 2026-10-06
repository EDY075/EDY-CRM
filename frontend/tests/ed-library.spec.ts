import {test,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test('biblioteca: edição, versões, desativação e foco; contexto chega ao pacote',async({page,request})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message))
 const lead=await(await request.post('/api/ed/empresas',{data:{nome:'Empresa fictícia · biblioteca',nicho:'Padarias',demonstracao:true}})).json()
 await page.goto('/biblioteca/skills?lead='+lead.id)
 await page.getByRole('button',{name:'Novo item',exact:true}).click()
 await expect(page.getByLabel('Título',{exact:true})).toBeFocused()
 await page.getByLabel('Título',{exact:true}).fill('Critério QA deste projeto')
 await page.getByLabel('Conteúdo revisado').fill('Preservar recortes aprovados deste projeto QA.')
 await page.getByRole('button',{name:'Salvar nova versão'}).click()
 const item=page.locator('.ed-library-item').filter({hasText:'Critério QA deste projeto'})
 await expect(item).toContainText('v1')
 await item.getByRole('button',{name:'Editar e versões'}).click()
 await page.getByLabel('Conteúdo revisado').fill('Preservar recortes e fontes deste projeto QA.')
 await page.getByRole('button',{name:'Salvar nova versão'}).click()
 await expect(item).toContainText('v2')
 const data=await(await request.get('/api/ed/biblioteca?tipo=skill&q=Critério%20QA')).json()
 const skill=data.items[0]
 const zip=await(await request.post(`/api/ed/empresas/${lead.id}/exportacoes`,{data:{}})).json()
 expect((await request.get(zip.zip_url)).ok()).toBeTruthy()
 const ctx=await(await request.get(`/api/ed/empresas/${lead.id}/contexto`)).json()
 expect(ctx.snapshot).toContainEqual(expect.objectContaining({id:skill.id,versao:2}))
 await item.getByRole('button',{name:'Arquivar',exact:true}).click()
 await expect(item).toContainText('arquivado')
 expect((await(await request.get(`/api/ed/empresas/${lead.id}/contexto`)).json()).items.some((x:{id:string})=>x.id===skill.id)).toBeFalsy()
 await item.getByRole('button',{name:'Restaurar',exact:true}).click()
 await expect(item).toContainText('ativo')
 await page.setViewportSize({width:390,height:844})
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()
 expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
 expect(errors).toEqual([])
})

test('produtos, processo, FAQ, galeria e rodapé têm quatro composições adequadas',async({page,request})=>{
 const lead=await(await request.post('/api/ed/empresas',{data:{nome:'Empresa fictícia · seções',demonstracao:true}})).json()
 await page.goto('/empresas/'+lead.id)
 await page.getByRole('button',{name:'Montar composição',exact:true}).click()
 for(const kind of ['produtos','processo','faq','galeria','rodape']){
  if(['produtos','processo','faq','galeria','rodape'].includes(kind)){
   await page.getByLabel('Tipo da nova seção').selectOption(kind)
   await page.getByRole('button',{name:'Incluir seção',exact:true}).click()
  }else await page.getByLabel('Seção em edição').selectOption(kind)
  const alternatives=page.locator('.ed-alternative .lp-'+kind)
  await expect(alternatives).toHaveCount(4)
  expect(await alternatives.evaluateAll(els=>new Set(els.map(e=>getComputedStyle(e).gridTemplateColumns+'|'+getComputedStyle(e).display+'|'+getComputedStyle(e).textAlign)).size)).toBeGreaterThan(1)
  if(kind==='faq')await expect(alternatives.first()).toContainText('Perguntas e respostas verificadas pendentes')
 }
 await page.emulateMedia({reducedMotion:'reduce'})
 await expect(page.locator('.lp-section h2').first()).toHaveCSS('animation-name','none')
})

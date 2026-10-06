import { useEffect,useRef,useState } from 'react'
import { Link,useNavigate,useSearchParams } from 'react-router-dom'
import { useMutation,useQuery,useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { httpClient } from '@/services/httpClient'
import { useAccess } from './accessContext'
import type { Empresa } from './types'
import { Badge,Erro,Field,Loading } from './shared'
import { visualStudioApi as api,type VisualStudio,type VisualApproval } from './visualStudioApi'
import { VisualProposals,VisualOperations,VisualMontage } from './VisualProposals'
import './visualStudio.css'

export function VisualStudioPanel({empresa}:{empresa:Empresa}){
 const [search]=useSearchParams()
 const [project,setProject]=useState(search.get('projeto')||''),[dirty,setDirty]=useState(false),[stage,setStage]=useState('visual'),base=useRef<VisualStudio|null>(null)
 const q=useQuery({queryKey:['ed','visual-studio',empresa.id,project],queryFn:()=>api.read(empresa.id,project)})
 if(q.data&&!dirty)base.current=q.data
 const shown=dirty?base.current:q.data
 return <section className="ed-visual-root" aria-label="Criar site"><div className="ed-panel ed-form"><div className="ed-panel-head"><div><span className="ed-eyebrow">ESTÚDIO VISUAL</span><h2>Criar site · {empresa.nome}</h2><p>Veja as propostas, escolha a composição e só então construa o site.</p></div><Badge>Escolha antes do HTML</Badge></div><Field label="Projeto desta direção visual"><select value={project} disabled={dirty} onChange={e=>setProject(e.target.value)}><option value="">Novo projeto desta empresa</option>{empresa.previas.filter(v=>v.construcao_id).map(v=><option key={v.id} value={v.construcao_id}>Projeto {v.construcao_id?.slice(0,8)} · {v.criado_em}</option>)}</select></Field></div>{q.isPending?<Loading/>:q.isError?<Erro error={q.error}/>:shown&&<StudioEditor key={empresa.id+'-'+project} company={empresa} initial={shown} onDirty={setDirty} stage={stage} onStage={setStage}/>}</section>
}

function StudioEditor({company,initial,onDirty,stage,onStage}:{company:Empresa;initial:VisualStudio;onDirty:(v:boolean)=>void;stage:string;onStage:(v:string)=>void}){
 const [state,setState]=useState(initial),[dirty,setDirty]=useState(false),[confirm,setConfirm]=useState(false)
 const client=useQueryClient(),navigate=useNavigate(),readonly=useAccess()?.ator?.papel==='leitura'
 const invalidate=()=>client.invalidateQueries({queryKey:['ed']})
 useEffect(()=>{if(!dirty&&initial.revisao>state.revisao)setState(initial)},[initial,dirty,state.revisao])
 const changed=(s:VisualStudio)=>{setState(s);setDirty(true);onDirty(true);setConfirm(false)}
 const save=useMutation({mutationFn:()=>api.save(company.id,state),onSuccess:saved=>{setState(saved);setDirty(false);onDirty(false);invalidate()}})
 const jobs=useQuery({queryKey:['ed','visual-jobs',company.id,state.projeto_id],queryFn:()=>api.jobs(company.id,state.projeto_id),refetchInterval:q=>q.state.data?.some(j=>['na_fila','pesquisando'].includes(j.estado))?1500:false})
 const brief=useQuery({queryKey:['ed','adaptativo',company.id,state.projeto_id],queryFn:()=>httpClient.get<{versao:number;revisao:{documental:string}}>(`/api/ed/empresas/${company.id}/adaptativo${state.projeto_id?'?projeto_id='+state.projeto_id:''}`)})
 const conversations=useQuery({queryKey:['ed','visual-conversations',company.id,state.projeto_id],queryFn:()=>httpClient.get<{id:string;titulo:string}[]>(`/api/ed/empresas/${company.id}/estudio/conversas${state.projeto_id?'?projeto_id='+state.projeto_id:''}`)})
 const build=useMutation({mutationFn:async(existing?:VisualApproval)=>{
  const a=existing||await api.approve(company.id,state,brief.data!.versao)
  return httpClient.post<{chat_id:string}>(`/api/ed/empresas/${company.id}/adaptativo/construir`,{versao:brief.data!.versao,projeto_id:state.projeto_id,chave:'visual-site:'+a.id,composicao_id:a.id,instrucoes:'Construa a página a partir da composição visual explicitamente aprovada. Preserve o brief revisado, copy, fatos, materiais e decisões. Imagens de interface são referências, não fundo da página. Reconstrua os componentes reais, compare recortes e escala em desktop/celular; não reproduza o template antigo reprovado.'})
 },onSuccess:r=>{invalidate();navigate('/assistente?chat='+r.chat_id)},onError:invalidate})
 const selected=state.escolhas.pagina?[{id:'pagina',titulo:'Página inteira',altura:1600}]:state.secoes
 const complete=selected.length>0&&selected.every(s=>state.variantes.some(v=>v.id===state.escolhas[s.id]&&v.direcao_versao===state.direcao.versao))
 const reviewed=!!brief.data?.versao&&['conforme','com_pendencias'].includes(brief.data.revisao.documental)
 const liveCount=useRef(0)
 useEffect(()=>{const count=jobs.data?.reduce((sum,j)=>sum+(j.resultados_parciais?.length||j.resultado?.variantes.length||0),0)||0;if(count!==liveCount.current){liveCount.current=count;client.invalidateQueries({queryKey:['ed','visual-studio',company.id,state.projeto_id]})}},[jobs.data,client,company.id,state.projeto_id])
 const disabled=readonly||dirty||save.isPending||build.isPending
 const approval=state.aprovacoes.at(-1)
 return <div className="ed-visual-studio"><nav className="ed-visual-steps" aria-label="Etapas para criar site">{[['visual','01','Visual'],['montagem','02','Montagem'],['site','03','Site'],['refinamentos','04','Refinamentos']].map(([id,n,label])=><button key={id} className={stage===id?'active':''} aria-pressed={stage===id} onClick={()=>onStage(id)}><span>{n}</span>{label}</button>)}</nav>
  {dirty&&<div className="ed-alert" role="status">Direção ou seções com edições não salvas. Salve antes de gerar, escolher ou aprovar.<button className="ed-button" disabled={save.isPending} onClick={()=>save.mutate()}>Salvar alterações</button></div>}
  {stage==='visual'&&<>
   <section className="ed-panel ed-form"><div className="ed-panel-head"><div><h3>Uma direção, várias composições</h3><p>Direção v{state.direcao.versao} · propostas candidatas. Nenhuma opção é aprovada automaticamente.</p></div><Badge>{state.variantes.length} propostas salvas</Badge></div>
    <details><summary>Direção visual e planejamento de seções</summary><div className="ed-form-grid"><Field label="Tipo de entrega"><select disabled={readonly} value={state.modo} onChange={e=>changed({...state,modo:e.target.value})}><option value="previa">Prévia para prospecção</option><option value="completo">Site completo · requisitos funcionais do brief</option></select></Field>{(['paleta','tipografia','estilo','composicao','movimento','invariantes'] as const).map(k=><Field key={k} label={{paleta:'Paleta',tipografia:'Tipografia',estilo:'Estilo e imagens',composicao:'Composição e ritmo',movimento:'Movimento e interações',invariantes:'O que preservar'}[k]}><textarea rows={2} maxLength={4000} value={state.direcao[k]} disabled={readonly} onChange={e=>changed({...state,direcao:{...state.direcao,[k]:e.target.value}})}/></Field>)}</div><p>Mudar a direção mantém o histórico e marca propostas anteriores como desatualizadas.</p>
    {state.secoes.map((s,i)=><div key={s.id} className="ed-visual-section-editor"><Field label={`Seção ${i+1} · título`}><input value={s.titulo} disabled={readonly} maxLength={4000} onChange={e=>changed({...state,secoes:state.secoes.map(x=>x.id===s.id?{...x,titulo:e.target.value}:x)})}/></Field><Field label={`Papel de ${s.titulo}`}><input value={s.papel} disabled={readonly} maxLength={4000} onChange={e=>changed({...state,secoes:state.secoes.map(x=>x.id===s.id?{...x,papel:e.target.value}:x)})}/></Field><Field label={`Copy revisada de ${s.titulo}`}><textarea rows={2} maxLength={4000} value={s.texto} disabled={readonly} onChange={e=>changed({...state,secoes:state.secoes.map(x=>x.id===s.id?{...x,texto:e.target.value}:x)})}/></Field><button className="ed-button" disabled={readonly||i===0} onClick={()=>{const list=[...state.secoes];[list[i-1],list[i]]=[list[i],list[i-1]];changed({...state,secoes:list})}}>Subir seção</button><button className="ed-button" disabled={readonly||state.secoes.length===1} onClick={()=>changed({...state,secoes:state.secoes.filter(x=>x.id!==s.id)})}>Remover do plano</button></div>)}
    <button className="ed-button" disabled={readonly||state.secoes.length>=30} onClick={()=>changed({...state,secoes:[...state.secoes,{id:'secao-'+crypto.randomUUID(),titulo:'Nova seção · revisar pertinência',texto:'',papel:'',altura:600}]})}><Plus size={16}/>Adicionar seção útil</button><button className="ed-button primary" disabled={readonly||!dirty||save.isPending} onClick={()=>save.mutate()}>Salvar direção e plano</button></details>
   </section><VisualProposals state={state} disabled={disabled} busy={jobs.data?.some(j=>['na_fila','pesquisando'].includes(j.estado))||false} onChanged={changed} onSaved={invalidate} onMontage={()=>onStage('montagem')}/>
  </>}
  {stage==='montagem'&&<section className="ed-panel ed-form"><h3>Revisar a composição escolhida</h3><p>Montagem visual para aprovação. Textos nas imagens serão substituídos pela copy revisada do brief.</p>{!complete&&<p className="ed-alert">Escolha uma proposta atual de página inteira ou uma para cada seção. Nenhum HTML será gerado com a montagem incompleta.</p>}<VisualMontage state={state}/><label className="ed-check"><input type="checkbox" disabled={disabled||!complete||!reviewed} checked={confirm} onChange={e=>setConfirm(e.target.checked)}/>Revisei a montagem e aprovo esta composição para construir. A aprovação comercial do titular continua pendente.</label>{!reviewed&&<p>Revise e salve o brief em <Link to={'/empresas/'+company.id+'?aba=preparacao'}>Preparar prévia</Link> antes de aprovar.</p>}<button className="ed-button primary" disabled={disabled||!confirm||!complete||!reviewed} onClick={()=>build.mutate(undefined)}>{build.isPending?'Aprovando versão e iniciando fila…':'Aprovar composição e gerar site'}</button>{approval&&<details><summary>Aprovação anterior · {approval.id.slice(0,8)}</summary><p>Brief v{approval.brief_versao} · direção v{approval.direcao.versao} · {approval.criado_em}. Escolhas novas não alteram esta versão.</p><button className="ed-button" disabled={disabled||!reviewed} onClick={()=>build.mutate(approval)}>Continuar com esta aprovação salva</button></details>}</section>}
  {stage==='site'&&<section className="ed-panel ed-form"><h3>Site e versões preservados</h3><p>O HTML usa o executor Codex existente depois da aprovação. Build e inspeção visual são etapas distintas.</p>{company.previas.length?company.previas.map(v=><p key={v.id}><a href={v.url} target="_blank" rel="noreferrer">Abrir prévia {v.construcao_id?.slice(0,8)||''} ↗</a><small>{v.observacoes}</small></p>):<p>Ainda sem prévia. Escolha a composição na etapa Montagem.</p>}<Link className="ed-button" to={'/empresas/'+company.id+'?aba=construir'}>Acompanhar construções e conversa</Link></section>}
  {stage==='refinamentos'&&<section className="ed-panel ed-form"><h3>Refinar na mesma conversa</h3><p>Refine a imagem na etapa Visual ou o site no chat de sua construção. Informe a seção e o que preservar. As versões anteriores e a aprovação ficam registradas.</p>{conversations.data?.length?conversations.data.map(c=><Link key={c.id} className="ed-button primary" to={'/assistente?chat='+c.id}>{c.titulo} · abrir mesma conversa</Link>):<p>Após aprovar e construir, a conversa vinculada aparecerá aqui. As conversas e prévias anteriores continuam em Prévia e versões.</p>}</section>}
  <VisualOperations company={company.id} jobs={jobs.data||[]} onChange={invalidate}/>
  {[save,build,jobs,brief,conversations].filter(m=>m.isError).map((m,i)=><Erro key={i} error={m.error}/>)}
 </div>
}

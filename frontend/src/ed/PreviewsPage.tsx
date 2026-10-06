import './assistant.css'
import {useState} from 'react'
import {useQuery} from '@tanstack/react-query'
import {Link} from 'react-router-dom'
import {httpClient} from '@/services/httpClient'
import {Badge,Loading,Erro,Field} from './shared'
import {RefinePreviewButton} from './PreviewActions'
import {previewLabels,type PreviewProject} from './previewState'
export function PreviewsPage(){
 const [search,setSearch]=useState('')
 const q=useQuery({queryKey:['ed','previas'],queryFn:()=>httpClient.get<PreviewProject[]>('/api/ed/previas')})
 const projects=q.data?.filter(p=>`${p.nome} ${p.nicho} ${p.cidade}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()))||[]
 return <><div className="ed-page-head"><div><h1>Prévias</h1><p>Abra um projeto ou continue o refinamento na conversa da empresa.</p></div><Link className="ed-button primary" to="/leads">Criar uma prévia</Link></div><Field label="Buscar prévia"><input type="search" placeholder="Empresa, nicho ou cidade" value={search} onChange={e=>setSearch(e.target.value)}/></Field>
 {q.isPending?<Loading/>:q.isError?<Erro error={q.error}/>:projects.length?<div className="ed-preview-projects">{projects.map(p=><article className="ed-panel ed-form" key={p.empresa_id}>
  <Link className="ed-preview-cover ed-preview-click" to={p.abrir_url} aria-label={'Abrir prévia de '+p.nome}>{p.miniatura_url?<img src={p.miniatura_url} alt={'Captura anterior da prévia de '+p.nome} loading="lazy"/>:<span>{p.nome.slice(0,1)}</span>}</Link>
  <div><h2>{p.nome}</h2><p>{p.nicho||'Nicho a revisar'} · {p.cidade||'Localização a revisar'}</p><Badge tone={p.estado==='disponivel'?'green':'amber'}>{previewLabels[p.estado]||p.estado}</Badge></div>
  <div className="ed-actions"><Link className="ed-button primary" to={p.abrir_url}>Abrir prévia</Link><RefinePreviewButton company={p.empresa_id} build={p.construcao_id}/></div>
  <details><summary>Versões e detalhes</summary><p>{p.versoes} versões preservadas. {p.motivo}</p><small>A miniatura é uma captura anterior; não comprova que o servidor esteja ativo.</small><Link className="ed-link" to={`/empresas/${p.empresa_id}?aba=previas`}>Abrir ficha e histórico</Link></details>
 </article>)}</div>:<section className="ed-panel ed-form"><h2>{search?'Nenhuma prévia nesta busca':'Da empresa à primeira prévia'}</h2><p>Revise uma empresa e escolha a composição antes de construir.</p><Link className="ed-button" to="/leads">Escolher empresa</Link></section>}</>
}

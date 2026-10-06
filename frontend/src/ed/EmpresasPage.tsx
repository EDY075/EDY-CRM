import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, ArrowUpRight, Search, Plus, FlaskConical, SlidersHorizontal } from 'lucide-react'
import { api } from './api'
import { Badge, Empty, Erro, Loading } from './shared'
import { date, etapas } from './domain'
import {crmApi,type CrmRecord} from './crmApi'
import {Field} from './shared'
import {LeadsNav} from './LeadsNav'
import {BatchPanel} from './BatchPanel'
import {AdaptiveSelection} from './AdaptivePanel'

export function EmpresasPage() {
  const navigate = useNavigate()
  const client = useQueryClient()
  const query = useQuery({ queryKey: ['ed', 'empresas'], queryFn: () => api.empresas(), retry: 1 })
  const config = useQuery({ queryKey: ['ed', 'config'], queryFn: api.config })
  const [q, setQ] = useState(''), [etapa, setEtapa] = useState(''), [city, setCity] = useState('')
  const [nicho, setNicho] = useState(''), [site, setSite] = useState(''), [duplicates, setDuplicates] = useState(false)
  const [sort, setSort] = useState('recente')
  const [viewName,setViewName]=useState('')
  const [selected,setSelected]=useState<string[]>([])
  const views=useQuery({queryKey:['ed','crm','visao'],queryFn:()=>crmApi.list('visao')})
  const saveView=useMutation({mutationFn:()=>crmApi.save('visao',{titulo:viewName,filtros:{q,etapa,cidade:city,nicho,site}}),onSuccess:()=>{setViewName('');client.invalidateQueries({queryKey:['ed','crm','visao']})}})
  function applyView(view:CrmRecord){const f=view.filtros as Record<string,string>;setQ(f.q||'');setEtapa(f.etapa||'');setCity(f.cidade||'');setNicho(f.nicho||'');setSite(f.site||'')}
  const all = query.data || []
  const filtered = useMemo(() => {
    const normalize = (text: string) => text.toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    const values = (query.data || []).filter(x => normalize(`${x.nome} ${x.nicho} ${x.cidade}`).includes(normalize(q))
      && (!etapa || x.etapa === etapa) && (!city || x.cidade === city) && (!nicho || x.nicho === nicho)
      && (!duplicates || x.possiveis_duplicatas.length > 0)
      && (!site || (site === 'informado' ? !!x.site : !x.site)))
    return values.sort((a, b) => sort === 'nome' ? a.nome.localeCompare(b.nome) : b.atualizado_em.localeCompare(a.atualizado_em))
  }, [query.data, q, etapa, city, nicho, site, duplicates, sort])
  const demo = useMutation({ mutationFn: () => api.criar({ nome: 'Ateliê Aurora — demonstração',
    nicho: 'Salões de beleza', cidade: 'Recife', uf: 'PE', demonstracao: true,
    observacoes: 'Empresa fictícia para experimentar o fluxo. Nenhuma informação representa uma empresa real.' }),
    onSuccess: async data => { await client.invalidateQueries({ queryKey: ['ed', 'empresas'] }); navigate(`/empresas/${data.id}`) } })
  return <>
    <AdaptiveSelection key={selected.join(',')} selected={selected}/>
    <div className="ed-page-head"><div><span className="ed-eyebrow">DO LEAD À PRÉVIA</span><h1>Empresas</h1><p>Revise informações e siga para a prévia.</p></div>
      <Link className="ed-button primary" to="/nova-busca"><Search size={17} /> Nova busca</Link></div>
    <LeadsNav/>
    <BatchPanel selected={selected} onCreated={()=>setSelected([])}/>
    {config.data && !config.data.osm_habilitado && <div className="ed-alert"><span className="ed-dot amber" /><span><strong>Fonte de pesquisa pendente.</strong> Ative o OpenStreetMap para buscar empresas ou comece por um cadastro manual.</span><Link to="/integracoes">Configurar <ArrowRight size={14} /></Link></div>}
    <section className="ed-panel">
      <div className="ed-panel-head"><div><h2>Empresas</h2><span>{filtered.length} {filtered.length === 1 ? 'registro' : 'registros'}</span></div><Link className="ed-button" to="/empresas/nova"><Plus size={16} /> Cadastro manual</Link></div>
      <div className="ed-toolbar"><label className="ed-search"><Search size={17} /><input aria-label="Buscar empresas" placeholder="Buscar empresa, nicho ou cidade…" value={q} onChange={e => setQ(e.target.value)} /></label>
        <select aria-label="Filtrar etapa" value={etapa} onChange={e => setEtapa(e.target.value)}><option value="">Todas as etapas</option>{Object.entries(etapas).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
        <select aria-label="Filtrar cidade" value={city} onChange={e => setCity(e.target.value)}><option value="">Todas as cidades</option>{[...new Set(all.map(x => x.cidade).filter(Boolean))].map(x => <option key={x}>{x}</option>)}</select>
        <select aria-label="Filtrar nicho" value={nicho} onChange={e => setNicho(e.target.value)}><option value="">Todos os nichos</option>{[...new Set(all.map(x => x.nicho).filter(Boolean))].map(x => <option key={x}>{x}</option>)}</select>
      </div>
      <details className="ed-form"><summary>Visualizações salvas deste workspace</summary><div className="ed-actions">{views.data?.items.map(v=><button key={v.id} className="ed-button" onClick={()=>applyView(v)}>{String(v.titulo)}</button>)}</div><Field label="Nome da visualização"><input maxLength={120} value={viewName} onChange={e=>setViewName(e.target.value)}/></Field><button className="ed-button" disabled={!viewName||saveView.isPending} onClick={()=>saveView.mutate()}>Salvar filtros atuais</button>{saveView.isError&&<Erro error={saveView.error}/>}</details>
      <div className="ed-subtoolbar"><SlidersHorizontal size={14} /><select aria-label="Filtrar situação do site" value={site} onChange={e => setSite(e.target.value)}><option value="">Qualquer situação do site</option><option value="informado">Site informado</option><option value="nao_informado">Site não informado</option></select>
        <label className="ed-check"><input type="checkbox" checked={duplicates} onChange={e => setDuplicates(e.target.checked)} /> Possíveis duplicatas</label>
        <select aria-label="Ordenar empresas" value={sort} onChange={e => setSort(e.target.value)}><option value="recente">Atualizadas recentemente</option><option value="nome">Nome A–Z</option></select></div>
      {query.isPending ? <Loading /> : query.isError ? <><Erro error={query.error} /><button className="ed-button" onClick={() => query.refetch()}>Tentar novamente</button></> : filtered.length ? <div className="ed-table-wrap"><table className="ed-table"><thead><tr><th><span className="ed-sr-only">Selecionar para lote</span></th><th>Empresa / nicho</th><th>Localização</th><th>Presença digital</th><th>Etapa</th><th>Atualizada</th><th><span className="ed-sr-only">Abrir ficha</span></th></tr></thead><tbody>
        {filtered.map(x => <tr key={x.id}><td><input type="checkbox" aria-label={"Selecionar "+x.nome+" para lote"} checked={selected.includes(x.id)} disabled={!selected.includes(x.id)&&selected.length>=5} onChange={e=>setSelected(v=>e.target.checked?[...v,x.id]:v.filter(i=>i!==x.id))}/></td><td><Link className="ed-company" to={`/empresas/${x.id}`}><span className="ed-initial">{x.nome.slice(0, 1)}</span><span><strong>{x.nome}</strong><small>{x.nicho || 'Nicho a confirmar'}</small><small className="ed-mobile-location">{[x.cidade, x.uf].filter(Boolean).join(' · ')}</small>{['academia','padaria','restaurante','salão','clinica','clínica'].includes(x.nome.trim().toLocaleLowerCase()) && <Badge tone="amber">Identidade a confirmar</Badge>}{x.demonstracao && <Badge tone="amber">Demonstração</Badge>}{x.possiveis_duplicatas.length > 0 && <Badge tone="amber">Possível duplicata</Badge>}</span></Link></td>
          <td>{x.cidade || 'A confirmar'}<small>{[x.bairro, x.uf].filter(Boolean).join(' · ')}</small></td><td><Badge tone={x.site ? 'green' : ''}>{x.site ? 'Site informado' : 'Site não informado'}</Badge><small>{x.instagram ? 'Instagram a conferir' : 'Instagram pendente'}</small></td><td><Badge tone={x.etapa === 'previa_pronta' ? 'green' : ''}>{etapas[x.etapa]}</Badge></td><td className="ed-muted">{date(x.atualizado_em)}</td><td><Link className="ed-icon-button" to={`/empresas/${x.id}`} aria-label={`Abrir ${x.nome}`}><ArrowUpRight size={18} /></Link></td></tr>)}
      </tbody></table></div> : <Empty title={all.length ? 'Nenhum registro com esses filtros' : 'Sua primeira oportunidade começa aqui'}>{all.length ? 'Ajuste os filtros para reencontrar suas empresas.' : 'Pesquise uma região ou cadastre uma empresa. Dados ausentes serão sinalizados na ficha.'}</Empty>}
      <footer className="ed-table-footer"><span>Fontes e pendências acompanham cada empresa.</span><span>Criação da landing page no Codex <ArrowUpRight size={14} /></span></footer>
    </section>
    <div className="ed-demo-line"><FlaskConical size={16} /><span>Quer conhecer o fluxo com uma empresa fictícia?</span><button className="ed-text-button" disabled={demo.isPending} onClick={() => demo.mutate()}>{demo.isPending ? 'Criando exemplo…' : 'Carregar demonstração'} <ArrowRight size={14} /></button></div>
    {demo.isError && <Erro error={demo.error} />}
  </>
}

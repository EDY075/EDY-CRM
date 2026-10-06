import { useState,useEffect,lazy,Suspense } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, MapPin, Building2, FileText, Image, Link2, CircleCheck, AlertCircle } from 'lucide-react'
import { api } from './api'
import {httpClient} from '@/services/httpClient'
import {RefinePreviewButton} from './PreviewActions'
import type {PreviewProject} from './previewState'
import { Badge, Erro, External, Loading } from './shared'
import { date, etapas } from './domain'
import { EmpresaForm } from './EmpresaForm'
import { MateriaisPanel } from './MateriaisPanel'
import { DocumentoPanel } from './DocumentoPanel'
import { PreviasPanel } from './PreviasPanel'
import { PesquisaSitePanel } from './PesquisaSitePanel'
import { PreparacaoPanel } from './PreparacaoPanel'
import { SiteAssociationPanel } from './SiteAssociationPanel'
import { ImageStudioPanel } from './ImageStudioPanel'
import { CompositionPanel } from './CompositionPanel'
import { SocialPanel } from './SocialPanel'
import { RuntimePanel } from './RuntimePanel'
import { ContextPanel } from './ContextPanel'
import { ProjectPanel } from './ProjectPanel'
import { AdaptivePanel } from './AdaptivePanel'
const LeadOperationsPanel=lazy(()=>import('./OperationalPage').then(m=>({default:m.LeadOperationsPanel})))
const ProspectPanel=lazy(()=>import('./ProspectPanel').then(m=>({default:m.ProspectPanel})))
const AssistantPage=lazy(()=>import('./AssistantPage').then(m=>({default:m.AssistantPage})))
const VisualStudioPanel=lazy(()=>import('./VisualStudioPanel').then(m=>({default:m.VisualStudioPanel})))

const tabs = [{ id: 'perfil', label: 'Ficha da empresa', icon: Building2 }, { id: 'operacao', label: 'Contatos e atividades', icon: Building2 }, { id: 'social', label: 'Instagram', icon: Link2 }, { id: 'materiais', label: 'Materiais', icon: Image },
  { id: 'pesquisa', label: 'Pesquisar empresa', icon: Building2 }, { id: 'studio', label: 'Estúdio de imagens', icon: Image }, { id: 'preparacao', label: 'Preparar prévia', icon: FileText }, { id: 'composicao', label: 'Montar composição', icon: FileText }, { id: 'documento', label: 'Documento e exportação', icon: FileText }, { id: 'construir', label: 'Construir prévia', icon: FileText }, { id: 'previas', label: 'Prévia e versões', icon: Link2 }]

export function FichaPage() {
  const { id = '' } = useParams(), client = useQueryClient()
  const [search] = useSearchParams()
  const [tab, setTab] = useState(tabs.some(t=>t.id===search.get('aba'))?search.get('aba')!:'perfil'), [edit, setEdit] = useState(false)
  useEffect(()=>{const target=search.get('aba');if(target&&(target==='visual'||tabs.some(t=>t.id===target)))setTab(target)},[search])
  const query = useQuery({ queryKey: ['ed', 'empresa', id], queryFn: () => api.empresa(id), retry: 1 })
  const previews=useQuery({queryKey:['ed','previas'],queryFn:()=>httpClient.get<PreviewProject[]>('/api/ed/previas')})
  const stage = useMutation({ mutationFn: (value: string) => api.salvar(id, { etapa: value }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['ed'] }) })
  if (query.isPending) return <Loading />
  if (query.isError) return <><Link className="ed-back" to="/leads"><ArrowLeft size={16} /> Empresas</Link><Erro error={query.error} /><button className="ed-button" onClick={() => query.refetch()}>Tentar novamente</button></>
  const lead = query.data
  return <>
    {lead.crm_unida_em&&<div className="ed-alert"><span>Registro unido; histórico e materiais originais preservados.</span><Link to={'/empresas/'+lead.crm_unida_em}>Abrir ficha consolidada ↗</Link></div>}
    {!!lead.crm_historicos_relacionados?.length&&<div className="ed-alert"><span>Históricos vinculados de empresas unidas:</span>{lead.crm_historicos_relacionados.map(i=><Link key={i} to={'/empresas/'+i}>Abrir origem ↗</Link>)}</div>}
    <Link className="ed-back" to="/leads"><ArrowLeft size={16} /> Todas as empresas</Link>
    <div className="ed-page-head ed-detail-head"><div><div className="ed-eyebrow">PERFIL DO ESTABELECIMENTO {lead.demonstracao && <Badge tone="amber">Demonstração — empresa fictícia</Badge>}</div><h1>{lead.nome}</h1><p><MapPin size={15} />{[lead.cidade, lead.uf, lead.bairro].filter(Boolean).join(' · ') || 'Localização a confirmar'}<span> / </span>{lead.nicho || 'Nicho a confirmar'}</p></div>
      <div className="ed-stage-select"><label htmlFor="etapa-ficha">Etapa do fluxo</label><select id="etapa-ficha" value={lead.etapa} disabled={stage.isPending} onChange={e => stage.mutate(e.target.value)}>{Object.entries(etapas).map(([value, name]) => <option key={value} value={value}>{name}</option>)}</select></div></div>
    {stage.isError && <Erro error={stage.error} />}
    {previews.data?.filter(p=>p.empresa_id===id).map(p=><div className="ed-actions ed-lead-preview" key={p.construcao_id}><Link className="ed-button primary" to={p.abrir_url}>Abrir prévia</Link><RefinePreviewButton company={id} build={p.construcao_id}/><small>Última versão selecionada · arquivos e histórico preservados</small></div>)}
    <div className="ed-flow-strip"><span><CircleCheck size={16} /> Informações com origem</span><span><Image size={16} /> {lead.materiais.filter(x => x.selecionado).length} materiais selecionados</span><span><FileText size={16} /> {lead.exportacoes.length} pacotes</span><span><Link2 size={16} /> {lead.previas.length} prévias</span></div>
    <button className="ed-button primary" onClick={()=>setTab('visual')} aria-pressed={tab==='visual'}>Criar site · Visual → Montagem → Site → Refinamentos</button>
    <nav className="ed-tabs" aria-label="Seções da ficha">{tabs.map(t => <button key={t.id} aria-pressed={tab === t.id} onClick={() => setTab(t.id)} className={tab === t.id ? 'active' : ''}><t.icon size={16} />{t.label}</button>)}</nav>
    {tab==='visual'&&<Suspense fallback={<Loading/>}><VisualStudioPanel key={lead.id} empresa={lead}/></Suspense>}
    {tab === 'perfil' && (edit ? <><button className="ed-button ed-edit-back" onClick={() => setEdit(false)}>Voltar à ficha</button><EmpresaForm key={lead.id} empresa={lead} onSaved={() => setEdit(false)} /></> : <><SiteAssociationPanel key={lead.site} empresa={lead} onEdit={() => setEdit(true)} onMaterials={() => setTab('materiais')} /><div className="ed-detail-grid">
      <section className="ed-panel ed-form"><div className="ed-panel-head"><h2>Informações comerciais</h2><button className="ed-button" onClick={() => setEdit(true)}>Editar ficha</button></div>
        <button className="ed-button" onClick={() => setTab('pesquisa')}>Pesquisar informações da empresa</button>
        <dl className="ed-facts">{[['Descrição', lead.descricao], ['Endereço', lead.endereco], ['Contato', lead.telefone], ['E-mail', lead.email], ['Serviços', lead.servicos], ['Horários', lead.horarios], ['Links sociais', lead.redes_sociais]].map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value || <span className="ed-muted">Não localizado · a confirmar</span>}</dd></div>)}
          <div><dt>Site</dt><dd>{lead.site ? <><External url={lead.site}>{lead.site}</External><small>{lead.associacao_site.estado === 'confirmado' ? 'Vínculo confirmado por você' : 'Candidato · associação a confirmar'}</small></> : 'Sem site confirmado · revisão pendente'}</dd></div><div><dt>Instagram</dt><dd>{lead.instagram ? <External url={lead.instagram}>{lead.instagram}</External> : 'Não localizado · a confirmar'}</dd></div></dl>
        <h3>Notas internas</h3><p className="ed-notes">{lead.observacoes || 'Nenhuma observação registrada.'}</p>
      </section>
      <aside className="ed-panel ed-form ed-pending" aria-label="Pendências da empresa"><h2><AlertCircle size={18} /> Pendências</h2><ul>{lead.pendencias.map(x => <li key={x}>{x}</li>)}</ul>
        {lead.possiveis_duplicatas.length > 0 && <><h3>Possíveis duplicatas</h3><p>Compare nome, contato e estabelecimento. Filiais diferentes podem compartilhar esses dados.</p>{lead.possiveis_duplicatas.map((x, i) => <Link key={x} to={`/empresas/${x}`}>Conferir registro {i + 1} ↗</Link>)}</>}
      </aside>
      <section className="ed-panel ed-form ed-sources"><div className="ed-section-title"><h2>Fontes por informação</h2><p>Valor, origem, data, retenção e estado de verificação.</p></div><div className="ed-table-wrap"><table className="ed-table"><thead><tr><th>Informação</th><th>Origem / fornecedor</th><th>Consulta</th><th>Verificação</th></tr></thead><tbody>{Object.entries(lead.fontes).map(([key, source]) => <tr key={key}><td><strong>{key}</strong><small>{source.valor}</small></td><td>{source.url ? <External url={source.url}>Ver fonte</External> : 'Cadastro manual'}<small>{source.fornecedor} · {source.retencao}</small></td><td>{date(source.consultado_em)}</td><td><Badge tone={source.verificacao === 'confirmado_usuario' ? 'green' : 'amber'}>{source.verificacao === 'confirmado_usuario' ? 'Confirmado por você' : 'A confirmar'}</Badge></td></tr>)}</tbody></table></div></section>
    </div></>)}
    {tab === 'materiais' && <MateriaisPanel key={lead.id} empresa={lead} />}
    {tab === 'operacao' && <Suspense fallback={<Loading/>}><LeadOperationsPanel company={lead.id} /></Suspense>}
    {tab === 'pesquisa' && <PesquisaSitePanel key={lead.id} empresa={lead} onEdit={() => { setEdit(true); setTab('perfil') }} onMaterials={() => setTab('materiais')} />}
    {tab === 'preparacao' && <><AdaptivePanel key={lead.id} company={lead.id}/><PreparacaoPanel key={lead.id} empresa={lead} /></>}
    {tab === 'studio' && <ImageStudioPanel key={lead.id} empresa={lead} />}
    {tab === 'composicao' && <><ContextPanel id={lead.id}/><CompositionPanel key={lead.id} empresa={lead} /></>}
    {tab === 'social' && <SocialPanel key={lead.id} empresa={lead} />}
    {tab === 'construir' && <><Suspense fallback={<Loading/>}><AssistantPage key={lead.id} initialCompany={lead.id}/></Suspense><details className="ed-panel ed-form"><summary>Contexto, construção direta e diagnóstico avançado</summary><ContextPanel id={lead.id}/><ProjectPanel empresa={lead}/><RuntimePanel key={lead.id} empresa={lead} /></details></>}
    {tab === 'documento' && <><Suspense fallback={<Loading/>}><ProspectPanel company={lead.id}/></Suspense><DocumentoPanel key={lead.id} empresa={lead} /></>}
    {tab === 'previas' && <PreviasPanel key={lead.id} empresa={lead} onReopen={() => setTab('construir')} />}
  </>
}

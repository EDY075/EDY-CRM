import { useState, lazy, Suspense } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Search, Check, AlertCircle } from 'lucide-react'
import { api } from './api'
import { Badge, Erro, External, Field, Loading,ResearchProgress } from './shared'
import { SiteAssociationPanel } from './SiteAssociationPanel'
const ConnectedResearchPanel = lazy(() => import('./ConnectedResearchPanel').then(m => ({ default: m.ConnectedResearchPanel })))
import type { Candidata, Empresa, Pesquisa } from './types'

const labels: Record<string, string> = { descricao: 'Descrição', telefone: 'Contato', email: 'E-mail', endereco: 'Endereço',
  horarios: 'Horários', servicos: 'Serviços', instagram: 'Instagram', redes_sociais: 'Links sociais' }
const active = (job?: Pesquisa | null) => !!job && ['na_fila', 'pesquisando'].includes(job.estado)

const errorLabels: Record<string, string> = { robots_regra: 'Regra de robots.txt', http: 'Resposta HTTP', rede: 'Falha de rede / TLS', interpretacao: 'Interpretação do conteúdo', conteudo: 'Formato de conteúdo', limite: 'Limite de coleta' }

export function PesquisaSitePanel({ empresa, onEdit, onMaterials }: { empresa: Empresa; onEdit: () => void; onMaterials: () => void }) {
  const client = useQueryClient(), [confirmed, setConfirmed] = useState(false)
  const [provider, setProvider] = useState('site_local')
  const connectors = useQuery({ queryKey: ['ed', 'integracoes'], queryFn: api.integracoesStatus })
  const firecrawl = connectors.data?.conectores.firecrawl
  const canFirecrawl = !!firecrawl?.credencial_presente
  const query = useQuery({ queryKey: ['ed', 'pesquisa', empresa.id], queryFn: () => api.pesquisa(empresa.id),
    refetchInterval: q => active(q.state.data) ? 1200 : false })
  const cancel = useMutation({ mutationFn: () => api.cancelarPesquisa(empresa.id, query.data!.id), onSuccess: () => client.invalidateQueries({ queryKey: ['ed'] }) })
  const diagnose = useMutation({ mutationFn: () => api.diagnosticarPesquisa(empresa.id, query.data!.id), onSuccess: () => client.invalidateQueries({ queryKey: ['ed', 'pesquisa', empresa.id] }) })
  const start = useMutation({ mutationFn: () => api.pesquisarSite(empresa.id, empresa.site, provider), onSuccess: async data => {
    client.setQueryData(['ed', 'pesquisa', empresa.id], data); await client.invalidateQueries({ queryKey: ['ed'] })
  } })
  return <div className="ed-research">
    <Suspense fallback={<Loading />}><ConnectedResearchPanel key={empresa.id} company={empresa.id} onMaterials={onMaterials} /></Suspense>
    <SiteAssociationPanel key={empresa.site} empresa={empresa} onEdit={onEdit} onMaterials={onMaterials} />
    <section className="ed-panel ed-form">
      <div className="ed-section-title"><h2>Pesquisar informações da empresa</h2><p>Leitura de até quatro páginas do site confirmado: início, serviços, sobre e contato. As sugestões só passam para a ficha depois da sua revisão.</p></div>
      <p>Site cadastrado: {empresa.site ? <External url={empresa.site}>{empresa.site}</External> : 'Cadastre o site na ficha para pesquisar.'}</p>
      <Field label="Fornecedor de enriquecimento"><select value={provider} disabled={active(query.data)} onChange={e => { setProvider(e.target.value); setConfirmed(false) }}><option value="site_local">Leitura local · sem credencial</option><option value="firecrawl" disabled={!canFirecrawl}>Firecrawl · {canFirecrawl ? `${firecrawl?.estado.replaceAll('_', ' ')}; requer créditos` : 'sem credencial'}</option></select></Field>
      <label className="ed-check"><input type="checkbox" checked={confirmed} disabled={!empresa.site || active(query.data)} onChange={e => setConfirmed(e.target.checked)} /> Confirmo que este site pertence a esta empresa e à filial que estou pesquisando.</label>
      <button className="ed-button primary" disabled={!confirmed || !empresa.site || start.isPending || active(query.data)} onClick={() => start.mutate()}><Search size={16} />{active(query.data) ? 'Pesquisando o site…' : 'Pesquisar informações da empresa'}</button>
      <small>Sem login, execução de scripts ou coleta de perfis sociais. Bloqueios, páginas dependentes de JavaScript e direitos de uso podem exigir revisão. Cadastro e upload manual continuam disponíveis.</small>
      {!empresa.site && <div className="ed-alert">Sem site confirmado. A leitura do site está indisponível; continue pelas fontes e materiais acima. Links de busca/mapa não serão usados como site oficial.</div>}
      <small>Firecrawl pode renderizar JavaScript quando disponível; continua sujeito à política do site. Uma regra proibitiva também é respeitada nessa fonte. Google Places e OpenStreetMap são fontes de descoberta, não substitutos da leitura deste site.</small>
      {start.isError && <Erro error={start.error} />}
    </section>
    {query.isPending ? <Loading /> : query.isError ? <Erro error={query.error} /> : query.data && <>
      <section className="ed-panel ed-form" aria-label="Progresso da pesquisa"><div className="ed-research-progress" role="status" aria-live="polite"><Badge tone={query.data.estado === 'concluida' ? 'green' : 'amber'}>{query.data.estado.replaceAll('_', ' ')}</Badge><p>{query.data.estado === 'erro' && !query.data.paginas.some(p => p.estado === 'lida') ? 'Nenhuma página lida. Pesquisa não concluída; veja a falha registrada e as ações disponíveis.' : query.data.mensagem}</p></div>
        <p>Execução: <code>{query.data.id}</code>{query.data.criado_em && <> · {new Date(query.data.criado_em).toLocaleString('pt-BR')}</>}<br />URL consultada: <External url={query.data.site}>{query.data.site}</External></p>
        <p>Origem: site confirmado da empresa · coletor: {query.data.fornecedor === 'firecrawl' ? 'Firecrawl' : 'leitura local'}. Imagens e links sociais continuam sujeitos à confirmação.</p>
        <ResearchProgress active={active(query.data)} failed={['erro','interrompida','cancelada','bloqueada'].includes(query.data.estado)} value={query.data.estado==='erro'?0:query.data.progresso} message={active(query.data)?'Lendo páginas e identificando informações disponíveis…':query.data.estado==='concluida'?'Leitura concluída · sugestões aguardam sua revisão':'Leitura encerrada · confira o resultado e as pendências'} label="Progresso da leitura do site"/>
        {!active(query.data) && <button className="ed-button" disabled={diagnose.isPending} onClick={() => diagnose.mutate()}>{diagnose.isPending ? 'Verificando robots.txt…' : 'Verificar política atual (somente robots.txt)'}</button>}
        {diagnose.isError && <Erro error={diagnose.error} />}
        {query.data.diagnostico_atual && <div className="ed-alert" role="status"><span><strong>Diagnóstico atual · {new Date(query.data.diagnostico_atual.consultado_em).toLocaleString('pt-BR')}</strong><br />{query.data.diagnostico_atual.mensagem}<br />A execução original abaixo permanece no histórico; este diagnóstico não coletou páginas da empresa.</span></div>}
        {active(query.data) && <button className="ed-button" disabled={cancel.isPending} onClick={() => cancel.mutate()}>Cancelar pesquisa</button>}
        {cancel.isError && <Erro error={cancel.error} />}
        {query.data.paginas.length > 0 && <ul className="ed-research-pages">{query.data.paginas.map((p, i) => <li key={i}><External url={p.url}>{p.url}</External> · {p.estado === 'lida' ? 'Lida' : 'Falha'}</li>)}</ul>}
        {query.data.erros.map((e, i) => <div key={i} className="ed-alert error" role="status"><AlertCircle size={16} /><span><strong>{errorLabels[e.tipo || ''] || 'Falha registrada'}</strong><br /><External url={e.url}>{e.url}</External><br />{e.mensagem}{e.etapa && <><br />Etapa: {e.etapa === 'robots' ? 'verificação de robots.txt' : 'leitura da página'}</>}</span></div>)}
        {!query.data.robots && query.data.erros.length > 0 && <p>Execução anterior ao diagnóstico detalhado. Use “Verificar política atual” antes de decidir por uma nova pesquisa; esse registro não comprova bloqueio de todo o domínio.</p>}
        {query.data.robots && <details className="ed-research-diagnostic"><summary>Ver regras e diagnóstico da leitura</summary><p>User-agent: <code>{query.data.robots.user_agent}</code><br />Parser: {query.data.robots.parser}</p>
          {query.data.robots.documentos.map(d => <p key={d.url}><External url={d.url}>{d.url}</External> · {d.estado}{d.http_status && ` · HTTP ${d.http_status}`}{d.url_final && d.url_final !== d.url && <> · URL final: <External url={d.url_final}>{d.url_final}</External></>}</p>)}
          <ul>{query.data.robots.avaliacoes.map((r, i) => <li key={i}><External url={r.url}>{r.url}</External> · {r.permitido ? 'Permitida pela política' : 'Bloqueada pela política'}<br />Grupo: {r.grupo} · {r.regra} · caminho: <code>{r.caminho}</code></li>)}</ul>
        </details>}
        {query.data.diagnostico_atual?.robots && <details><summary>Regras verificadas agora</summary><p>User-agent: <code>{query.data.diagnostico_atual.robots.user_agent}</code> · {query.data.diagnostico_atual.robots.parser}</p>{query.data.diagnostico_atual.robots.documentos.map(d => <p key={d.url}><External url={d.url}>{d.url}</External> · {d.estado}{d.http_status && ` · HTTP ${d.http_status}`}{d.url_final && d.url_final !== d.url && <> · URL final: <External url={d.url_final}>{d.url_final}</External></>}</p>)}<ul>{query.data.diagnostico_atual.robots.avaliacoes.map((r, i) => <li key={i}>{r.caminho} · {r.permitido ? 'Permitida' : 'Bloqueada'} · Grupo: {r.grupo} · {r.regra}</li>)}</ul></details>}
        {['erro', 'parcial', 'sem_resultados'].includes(query.data.estado) && <div className="ed-alert"><span>As edições da ficha foram preservadas. Revise o site ou continue pelo cadastro e upload manual. {canFirecrawl ? 'Você pode escolher Firecrawl acima e confirmar a URL para tentar a fonte; o resultado ainda depende do fornecedor e da política.' : 'Firecrawl indisponível: configure uma credencial antes de tentar essa fonte.'}</span></div>}
        {query.data.pendencias.filter(p => query.data!.paginas.some(page => page.estado === 'lida') || !p.includes('JavaScript')).map(p => <small key={p}>{p}</small>)}
      </section>
      <Revisao key={query.data.id} empresa={empresa} pesquisa={query.data} />
    </>}
  </div>
}

function Revisao({ empresa, pesquisa }: { empresa: Empresa; pesquisa: Pesquisa }) {
  const client = useQueryClient()
  const [selected, setSelected] = useState<Record<string, { id: string; valor_atual: string }>>({})
  const [reviewed, setReviewed] = useState(false)
  const apply = useMutation({ mutationFn: () => api.aplicarSugestoes(empresa.id, pesquisa.id, Object.values(selected)),
    onSuccess: async () => { setSelected({}); setReviewed(false); await client.invalidateQueries({ queryKey: ['ed'] }) } })
  const jobSiteChanged = empresa.site !== pesquisa.site
  return <>
    <section className="ed-panel ed-form">
      <div className="ed-section-title"><h2>Sugestões para revisar</h2><p>Compare os dois valores. Escolha uma sugestão por campo; campos não escolhidos mantêm suas edições.</p></div>
      {jobSiteChanged && <div className="ed-alert">O site da ficha mudou. Faça uma nova pesquisa antes de aplicar estas sugestões.</div>}
      {pesquisa.sugestoes.length === 0 && <p className="ed-muted">Ainda não há sugestões disponíveis.</p>}
      <div className="ed-suggestion-list">{pesquisa.sugestoes.map(s => <article key={s.id} className="ed-suggestion">
        <div className="ed-suggestion-head"><strong>{labels[s.campo] || s.campo}</strong><Badge tone={s.aplicado ? 'green' : 'amber'}>{s.aplicado ? 'Aplicada após revisão' : 'Confirmação necessária'}</Badge></div>
        <dl><div><dt>Na ficha</dt><dd>{String(empresa[s.campo] || 'Não informado')}</dd></div><div><dt>Sugestão</dt><dd>{s.valor}</dd></div></dl>
        <small>{s.metodo}</small><p className="ed-evidence">Evidência: {s.evidencia}</p><External url={s.origem}>Ver página de origem</External>
        <label className="ed-check"><input type="checkbox" disabled={jobSiteChanged || active(pesquisa) || apply.isPending} checked={selected[s.campo]?.id === s.id} onChange={e => {
          setReviewed(false)
          setSelected(prev => { const next = { ...prev }; if (e.target.checked) next[s.campo] = { id: s.id, valor_atual: String(empresa[s.campo] || '') }; else delete next[s.campo]; return next })
        }} />{empresa[s.campo] ? 'Substituir este campo após conferir' : 'Preencher este campo após conferir'}: {labels[s.campo] || s.campo}</label>
      </article>)}</div>
      {pesquisa.sugestoes.length > 0 && <><label className="ed-check"><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} /> Conferi a identidade, a filial e os valores escolhidos. Confirmo a aplicação destas informações.</label>
        <button className="ed-button primary" disabled={!reviewed || !Object.keys(selected).length || apply.isPending || jobSiteChanged || active(pesquisa)} onClick={() => apply.mutate()}><Check size={16} />Confirmar sugestões selecionadas</button></>}
      {apply.isError && <Erro error={apply.error} />}{apply.isSuccess && <p className="ed-success" role="status">Sugestões aplicadas. Relatório, briefing e prompt atualizados; decisões manuais preservadas.</p>}
    </section>
    <section className="ed-panel ed-form"><div className="ed-section-title"><h2>Imagens candidatas</h2><p>Prévias para revisão. A origem não comprova permissão de uso. Importe com autorização e depois selecione na galeria para incluir no ZIP.</p></div>
      {pesquisa.imagens.length === 0 ? <p className="ed-muted">Nenhuma imagem candidata localizada até agora. Use o upload manual na aba Materiais.</p> :
        <div className="ed-gallery">{pesquisa.imagens.map(image => <ImagemCandidata key={image.id} image={image} empresa={empresa.id} pesquisa={pesquisa.id} />)}</div>}
    </section>
  </>
}

function ImagemCandidata({ image, empresa, pesquisa }: { image: Candidata; empresa: string; pesquisa: string }) {
  const client = useQueryClient(), [failed, setFailed] = useState(false), [authorized, setAuthorized] = useState(false), [attribution, setAttribution] = useState('')
  const upload = useMutation({ mutationFn: () => api.importarCandidata(empresa, pesquisa, image.id, attribution),
    onSuccess: () => client.invalidateQueries({ queryKey: ['ed'] }) })
  return <article className="ed-material">
    {failed ? <div className="ed-candidate-unavailable">Prévia indisponível. Confira a origem ou use upload manual.</div> : <img src={image.previa_url} alt={image.descricao || `Candidata a ${image.categoria}; identidade a conferir`} loading="lazy" onError={() => setFailed(true)} />}
    <div className="ed-material-body"><strong>{image.descricao || 'Imagem do site'}</strong><Badge tone="amber">{image.categoria} · categoria sugerida</Badge>
      <External url={image.origem}>Página de origem</External><External url={image.url}>Arquivo original</External>
      {image.material_id || upload.isSuccess ? <p className="ed-success" role="status">Importada. Selecione na aba Materiais para exportar.</p> : <form onSubmit={e => { e.preventDefault(); upload.mutate() }}>
        <Field label="Titular / atribuição da candidata"><input maxLength={1000} required value={attribution} onChange={e => setAttribution(e.target.value)} /></Field>
        <label className="ed-check"><input type="checkbox" checked={authorized} onChange={e => setAuthorized(e.target.checked)} /> Tenho permissão para exportar e usar esta imagem.</label>
        <button className="ed-button" disabled={!authorized || !attribution.trim() || upload.isPending}>Importar para a galeria</button>
        {upload.isError && <Erro error={upload.error} />}
      </form>}
    </div>
  </article>
}

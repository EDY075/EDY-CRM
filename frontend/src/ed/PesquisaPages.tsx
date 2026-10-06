import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Search, Plug, RotateCcw, Square, MapPin } from 'lucide-react'
import { api } from './api'
import { Badge, Empty, Erro, External, Field, Loading,ResearchProgress } from './shared'
import { date, estados } from './domain'
import { ConnectorCards } from './ConnectorCards'
import {DestinationCards} from './DestinationCards'
import { LocalConnectionTest } from './LocalConnectionTest'
import { RuntimeCard } from './RuntimePanel'
import {LeadsNav} from './LeadsNav'

export function BuscaPage() {
  const navigate = useNavigate(), client = useQueryClient()
  const config = useQuery({ queryKey: ['ed', 'config'], queryFn: api.config })
  const [nicho, setNicho] = useState('Salões de beleza'), [cidade, setCidade] = useState('')
  const [uf, setUf] = useState('PE'), [bairro, setBairro] = useState(''), [limite, setLimite] = useState(2)
  const [prioridade,setPrioridade]=useState('padrao')
  const mutation = useMutation({ mutationFn: () => api.buscar({ nicho, cidade, uf, bairro, limite,prioridade }),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ['ed', 'campanhas'] }); navigate('/campanhas') } })
  return <>
    <div className="ed-page-head"><div><span className="ed-eyebrow">DESCOBERTA</span><h1>Pesquisar empresas</h1><p>Escolha um nicho e uma localização para pesquisar na fonte configurada.</p></div></div>
    <LeadsNav/>
    {config.isPending ? <Loading /> : config.isError ? <Erro error={config.error} /> : <div className="ed-two-col">
      <form className="ed-panel ed-form" onSubmit={e => { e.preventDefault(); mutation.mutate() }}>
        <div className="ed-section-title"><h2>Nova pesquisa</h2><p>Comece com uma ou duas empresas; amplie depois de revisar.</p></div>
        <Field label="Nicho"><select value={nicho} onChange={e => setNicho(e.target.value)}>{config.data.nichos.map(x => <option key={x}>{x}</option>)}</select></Field>
        <div className="ed-form-grid"><Field label="Cidade"><input required maxLength={120} placeholder="Ex.: Recife" value={cidade} onChange={e => setCidade(e.target.value)} /></Field><Field label="UF"><select value={uf} onChange={e => setUf(e.target.value)}>{'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split(' ').map(x => <option key={x}>{x}</option>)}</select></Field></div>
        <Field label="Quantidade máxima"><input type="number" min={1} max={50} required value={limite} onChange={e => setLimite(Number(e.target.value))} /></Field>
        <details><summary>Filtros adicionais e prioridade</summary>        <Field label="Bairro (opcional)" hint="Só retornam registros com esse bairro informado no OSM; a cobertura pode ser pequena."><input maxLength={120} value={bairro} onChange={e => setBairro(e.target.value)} placeholder="Deixe vazio para buscar no município" /></Field>
        <Field label="Prioridade entre os registros retornados" hint="A ordenação usa campos do OSM; site ausente não comprova ausência de site. Busca por raio ainda não suportada; use município/bairro."><select value={prioridade} onChange={e=>setPrioridade(e.target.value)}><option value="padrao">Ordem da fonte</option><option value="site_ausente">Site não informado na fonte</option><option value="contato_disponivel">Telefone disponível para revisão</option></select></Field>
</details>
        {!config.data.osm_habilitado && <div className="ed-alert">Fonte pendente. <Link to="/integracoes">Configurar OpenStreetMap <ArrowRight size={14} /></Link></div>}
        {mutation.isError && <Erro error={mutation.error} />}
        {mutation.isPending&&<ResearchProgress active message="Registrando pesquisa na fila…"/>}
        <button className="ed-button primary" disabled={!config.data.osm_habilitado || mutation.isPending}><Search size={16} />{mutation.isPending ? 'Iniciando…' : 'Pesquisar empresas'}</button>
      </form>
      <aside className="ed-explainer" aria-label="Como funciona a pesquisa"><span className="ed-line-icon"><MapPin size={26} /></span><h2>Informação com origem.</h2><p>Esta busca consulta estabelecimentos mapeados no OpenStreetMap. O número escolhido é um limite, não uma promessa de resultados.</p><ol><li>Localizar cidade e estado</li><li>Consultar estabelecimentos do nicho</li><li>Relacionar resultados e detectar repetidos</li><li>Conferir cada ficha antes de exportar</li></ol><p className="ed-muted">Salões e barbearias compartilham a categoria de cabelo do OSM. Confirme o nicho, o bairro e o estabelecimento. Site não informado não comprova ausência de site.</p></aside>
    </div>}
  </>
}

export function CampanhasPage() {
  const client = useQueryClient()
  const companies=useQuery({queryKey:['ed','empresas'],queryFn:()=>api.empresas()})
  const query = useQuery({ queryKey: ['ed', 'campanhas'], queryFn: api.campanhas, refetchInterval: q =>
    q.state.data?.some(x => ['na_fila', 'pesquisando'].includes(x.estado)) ? 1500 : false })
  const action = useMutation({ mutationFn: ({ id, acao }: { id: string; acao: string }) => api.campanha(id, acao),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ['ed'] }) } })
  return <>
    <div className="ed-page-head"><div><span className="ed-eyebrow">HISTÓRICO DE PESQUISA</span><h1>Histórico de pesquisas</h1><p>Resultados parciais, falhas e retomadas ficam registrados.</p></div><Link className="ed-button primary" to="/nova-busca"><Search size={16} /> Nova busca</Link></div>
    <LeadsNav/>
    {action.isError && <Erro error={action.error} />}
    {query.isPending ? <Loading /> : query.isError ? <Erro error={query.error} /> : query.data.length === 0 ? <section className="ed-panel"><Empty title="Nenhuma pesquisa ainda">Comece por um nicho e uma cidade. Você também pode cadastrar uma empresa manualmente.</Empty></section> : <div className="ed-campaign-list">{query.data.map(job => <section key={job.id} className="ed-panel ed-campaign">
      <header><div><h2>{job.nicho}</h2><p>{job.cidade}, {job.uf}{job.bairro ? ` · ${job.bairro}` : ''}</p></div><Badge tone={job.estado === 'concluida' ? 'green' : 'amber'}>{estados[job.estado]}</Badge></header>
      <div className="ed-campaign-count"><strong>{job.encontrados}</strong><span>empresas relacionadas<small>{job.novos} novas · {job.repetidos} registros reencontrados · limite {job.limite}</small></span></div>
      <ResearchProgress active={['na_fila','pesquisando'].includes(job.estado)} value={job.progresso??(job.estado==='concluida'?100:undefined)} failed={['erro','interrompida','cancelada'].includes(job.estado)} message={job.mensagem}/>
      {!!job.historico_execucoes?.length && <details><summary>Execuções anteriores ({job.historico_execucoes.length})</summary>{job.historico_execucoes.map((run,i)=><p key={run.execucao_id||i}>{date(run.iniciado_em||job.criado_em)} · {estados[run.estado]||run.estado} · {run.encontrados} resultados. {run.mensagem}</p>)}</details>}
      <div className="ed-campaign-links">{job.empresa_ids.map((id) => <Link key={id} to={`/empresas/${id}`}>{companies.data?.find(x=>x.id===id)?.nome||'Empresa pendente de identificação'} <ArrowRight size={14} /></Link>)}</div>
      <footer><small>{date(job.criado_em)} · OpenStreetMap</small>{['na_fila', 'pesquisando'].includes(job.estado) ? <button className="ed-button" disabled={action.isPending} onClick={() => action.mutate({ id: job.id, acao: 'cancelar' })}><Square size={14} /> Cancelar busca</button> : ['erro', 'cancelada', 'interrompida', 'parcial', 'sem_resultados'].includes(job.estado) && <button className="ed-button" disabled={action.isPending} onClick={() => action.mutate({ id: job.id, acao: 'retomar' })}><RotateCcw size={14} /> Retomar</button>}</footer>
    </section>)}</div>}
  </>
}

export function IntegracoesPage({embedded=false}:{embedded?:boolean}) {
  const client = useQueryClient()
  const query = useQuery({ queryKey: ['ed', 'config'], queryFn: api.config })
  const campaigns = useQuery({ queryKey: ['ed', 'campanhas'], queryFn: api.campanhas })
  const local = useQuery({ queryKey: ['ed', 'integracoes-status'], queryFn: api.integracoesStatus })
  const mutation = useMutation({ mutationFn: api.configurar, onSuccess: () => client.invalidateQueries({ queryKey: ['ed'] }) })
  return <>
    {!embedded&&<div className="ed-page-head"><div><span className="ed-eyebrow">FONTES & ACESSO</span><h1>Integrações<span>.</span></h1><p>Escolha de onde vêm as informações. A exportação funciona sem IA.</p></div></div>}
    <section className="ed-connection-group"><h2>Criar com IA</h2><RuntimeCard/></section>
    <DestinationCards/>
    <h2>Encontrar empresas, fotos e referências</h2>
    {query.isPending ? <Loading /> : query.isError ? <Erro error={query.error} /> : <div className="ed-integrations">
      <section className="ed-panel ed-form"><div className="ed-integration-head"><span className="ed-line-icon"><MapPin size={25} /></span><div><h2>OpenStreetMap</h2><p>Nominatim + Overpass · sem credencial</p></div><Badge tone={query.data.osm_habilitado ? 'green' : 'amber'}>{!query.data.osm_habilitado ? 'Fonte desativada' : campaigns.data?.[0]?.estado === 'concluida' ? 'Conectado · última campanha concluída' : 'Ativo · conferir última campanha'}</Badge></div>
        <p>Última execução: {campaigns.data?.[0] ? `${date(campaigns.data[0].criado_em)} · ${campaigns.data[0].estado}` : 'nenhuma nesta base'}. Consumo financeiro: não informado. <Link to="/nova-busca">Testar com uma busca de 1 empresa</Link>.</p><p>Fonte pública de estabelecimentos por categoria e município. Cobertura e informações dependem das contribuições do mapa.</p><p>Ao ativar, as buscas enviam nicho e localização aos serviços públicos. O app limita a uma campanha por minuto, mantém cache da localização e inclui a atribuição ODbL no documento.</p>
        <div className="ed-source-links"><External url="https://operations.osmfoundation.org/policies/nominatim/">Política do Nominatim</External><External url="https://www.openstreetmap.org/copyright">Licença dos dados</External></div>
        <button className="ed-button primary" disabled={mutation.isPending} onClick={() => mutation.mutate(!query.data.osm_habilitado)}><Plug size={16} />{mutation.isPending ? 'Salvando…' : query.data.osm_habilitado ? 'Desativar fonte' : 'Ativar OpenStreetMap'}</button>
        <p>Diagnóstico do teste: {local.data?.locais.osm.estado || 'Ainda não validado nesta configuração'}. {local.data?.locais.osm.data && date(local.data.locais.osm.data)}</p>
        <LocalConnectionTest enabled={query.data.osm_habilitado} />
        {mutation.isError && <Erro error={mutation.error} />}
      </section>
      <section className="ed-panel ed-form"><div className="ed-section-title"><h2>Cadastro e materiais manuais</h2><p>Disponíveis sempre · sem conexão externa</p></div><p>Cadastre informações verificadas, informe a origem e envie imagens que você pode utilizar. Use URLs de Instagram como referência e confirme a identidade antes de marcar as informações.</p><Link className="ed-button" to="/empresas/nova">Cadastrar empresa <ArrowRight size={16} /></Link></section>
      <section className="ed-panel ed-form"><div className="ed-section-title"><h2>Site confirmado da empresa</h2><p>Disponível · leitura local sem credenciais</p></div><p>Na ficha, pesquise informações comerciais e imagens candidatas. Revise valores e vínculos sociais antes de aplicar; autorize e selecione materiais para exportar.</p><p>Última leitura: {local.data?.locais.site.criado_em ? `${date(local.data.locais.site.criado_em)} · ${local.data.locais.site.estado}` : 'nenhuma'}. Consumo: sem medição financeira.</p>{local.data?.locais.site.empresa_id && <Link className="ed-button" to={`/empresas/${local.data.locais.site.empresa_id}`}>Testar leitura na ficha da empresa</Link>}</section>
      <ConnectorCards />
    </div>}
  </>
}

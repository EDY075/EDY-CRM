import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, Link2, MapPin, Settings } from 'lucide-react'
import { httpClient } from '@/services/httpClient'
import { api } from './api'
import { Badge, Erro, Loading, ResearchProgress } from './shared'
import type { Operation } from './preparationTypes'

interface CaptureResult { biblioteca_id?: string; capturas?: { viewport: string; url: string }[] }
interface Readiness {
  skill: { instalada: boolean; atual: boolean; estado: string; versao: number | null; selecionada_empresa: boolean }
  selecao_sha256: string
  instagram: { estado: string; url?: string }
  maps_url: string; captura_disponivel: boolean; capturas: Operation<CaptureResult>[]
  fontes: { id: string; nome: string; estado: string; credencial_presente: boolean; acao_necessaria: string; operacoes_validadas: Record<string, string> }[]
}
const active = (job?: Operation) => ['na_fila', 'pesquisando'].includes(job?.estado || '')
const states: Record<string, string> = { nao_configurado: 'Sem credencial', configurado_nao_testado: 'Configurado · ainda não testado', autenticacao_validada: 'Autenticação validada · coleta pendente', operacao_validada: 'Operação validada', limitado: 'Acesso limitado', acesso_insuficiente: 'Permissão insuficiente', expirado_ou_recusado: 'Credencial recusada', cota_limite: 'Limite do fornecedor', erro: 'Erro' }

export function ConnectedResearchPanel({ company, onMaterials }: { company: string; onMaterials: () => void }) {
  const client = useQueryClient(), [chosenJob, setChosenJob] = useState(''), ticket = useRef('')
  const root = `/api/ed/empresas/${company}/pesquisa-conectada`
  const refresh = () => client.invalidateQueries({ queryKey: ['ed'] })
  const q = useQuery({ queryKey: ['ed', 'pesquisa-conectada', company], queryFn: () => httpClient.get<Readiness>(root) })
  const jobId = chosenJob || q.data?.capturas[0]?.id || ''
  const job = useQuery({ queryKey: ['ed', 'operacao', jobId], enabled: !!jobId,
    queryFn: () => api.operacao(jobId) as Promise<Operation<CaptureResult>>, refetchInterval: query => active(query.state.data) ? 1200 : false })
  const install = useMutation({ mutationFn: () => httpClient.post('/api/ed/pesquisa-conectada/skill', {}), onSuccess: refresh })
  const useSkill = useMutation({ mutationFn: () => httpClient.post(root + '/skill', { selecao_sha256: q.data!.selecao_sha256 }), onSuccess: refresh })
  const start = useMutation({ mutationFn: () => {
    ticket.current ||= crypto.randomUUID()
    return httpClient.post<Operation<CaptureResult>>(root + '/capturar-instagram', { chave: ticket.current })
  }, onSuccess: data => { ticket.current = ''; setChosenJob(data.id); client.setQueryData(['ed', 'operacao', data.id], data); refresh() } })
  const cancel = useMutation({ mutationFn: () => api.cancelarOperacao(jobId), onSuccess: refresh })
  const jobState = job.data?.estado
  useEffect(() => {
    if (jobState && !['na_fila', 'pesquisando'].includes(jobState)) client.invalidateQueries({ queryKey: ['ed', 'pesquisa-conectada', company] })
  }, [client, company, jobState, jobId])
  if (q.isPending) return <Loading />
  if (q.isError) return <section className="ed-panel ed-form"><Erro error={q.error} /><button className="ed-button" onClick={() => q.refetch()}>Recarregar fontes</button></section>
  const data = q.data, busy = active(job.data) || data.capturas.some(active)
  return <section className="ed-panel ed-form" aria-labelledby="connected-research-title">
    <div className="ed-section-title"><h2 id="connected-research-title">Pesquisa conectada</h2><p>Site, Instagram e materiais da mesma empresa. Revise a associação antes de importar; as suas edições ficam preservadas.</p></div>
    <div className="ed-connected-actions">
      <a className="ed-button" href={data.maps_url} target="_blank" rel="noopener noreferrer"><MapPin size={16} />Abrir Google Maps</a>
      <Link className="ed-button" to={`/empresas/${company}?aba=social`}><Link2 size={16} />Pesquisar / confirmar Instagram</Link>
      <button className="ed-button" onClick={onMaterials}>Enviar materiais</button>
    </div>
    <small>Maps abre uma consulta manual com nome e localização; não importa dados nem fotos. No Instagram, os conectores disponíveis consultam informações e arquivos de mídia, inclusive carrosséis.</small>
    <div className="ed-connected-capture">
      <div><strong>Prints do perfil</strong><p>{data.captura_disponivel ? data.instagram.url : 'Associação do Instagram pendente. Confirme o perfil e as evidências na etapa Instagram.'}</p></div>
      <button className="ed-button" aria-describedby="connected-capture-help" disabled={!data.captura_disponivel || start.isPending || busy} onClick={() => start.mutate()}><Camera size={16} />{busy ? 'Capturando…' : 'Capturar perfil público'}</button>
    </div>
    <small id="connected-capture-help">Captura desktop e celular sem usar seu login. Bloqueios, login obrigatório ou conteúdo incompleto encerram a tentativa com erro. Prints são referências para revisão, não fotos de produto autorizadas.</small>
    {[start.error, install.error, useSkill.error, job.error, cancel.error].filter(Boolean).map((e, i) => <Erro key={i} error={e} />)}
    {job.data && <div className="ed-connected-result">
      <ResearchProgress active={active(job.data)} failed={['erro', 'cancelada', 'interrompida'].includes(job.data.estado)} value={job.data.estado === 'erro' ? 0 : job.data.progresso} message={job.data.mensagem} label="Progresso da captura do Instagram" />
      {active(job.data) && <button className="ed-button" disabled={cancel.isPending} onClick={() => cancel.mutate()}>Cancelar captura</button>}
      {job.data.estado === 'concluida' && <><p>Capturas salvas como referências inativas. Confira a página, a identidade e os direitos antes de usar.</p><Link className="ed-text-button" to="/biblioteca/referencias">Revisar na Biblioteca →</Link></>}
      {job.data.resultado?.capturas && <div className="ed-reference-captures">{job.data.resultado.capturas.map(c => <figure key={c.viewport}><img loading="lazy" src={c.url} alt={`Print do perfil confirmado · ${c.viewport}`} /><figcaption>{c.viewport} · referência pendente de revisão</figcaption></figure>)}</div>}
      {data.capturas.length > 1 && <details><summary>Capturas anteriores</summary>{data.capturas.map(c => <button key={c.id} className="ed-text-button" onClick={() => setChosenJob(c.id)}>{c.estado.replaceAll('_', ' ')} · {c.id.slice(0, 8)}</button>)}</details>}
    </div>}
    <details><summary>Conexões e skill de pesquisa</summary>
      <p>A skill organiza o processo; cada fonte depende do seu acesso. Um teste de login não comprova uma coleta.</p>
      <div className="ed-connected-sources">{data.fontes.map(f => <div key={f.id}><strong>{f.nome}</strong><Badge tone={f.estado === 'operacao_validada' ? 'green' : 'amber'}>{states[f.estado] || f.estado}</Badge><small>{f.acao_necessaria}</small><small>{Object.keys(f.operacoes_validadas).length ? `Operações registradas: ${Object.keys(f.operacoes_validadas).join(', ')}` : 'Nenhuma operação específica validada nesta configuração.'}</small></div>)}</div>
      <Link className="ed-button" to="/configuracoes/conexoes"><Settings size={16} />Configurar conexões</Link>
      <p>EDY Pesquisa Conectada · {data.skill.instalada ? `v${data.skill.versao} · ${data.skill.estado === 'ativo' ? 'ativa' : 'inativa'}` : 'Disponível no projeto'}. A Biblioteca preserva as versões e a seleção de contexto de cada empresa.</p>
      {!data.skill.atual && <button className="ed-button" disabled={install.isPending} onClick={() => install.mutate()}>{install.isPending ? 'Salvando skill…' : data.skill.instalada ? 'Atualizar skill de pesquisa' : 'Ativar skill de pesquisa'}</button>}
      {data.skill.instalada && data.skill.estado === 'ativo' && !data.skill.selecionada_empresa && <button className="ed-button" disabled={useSkill.isPending} onClick={() => useSkill.mutate()}>Usar skill nesta empresa</button>}
      {data.skill.selecionada_empresa && <p className="ed-success" role="status">Skill incluída no contexto selecionado desta empresa. Próximas execuções registram sua versão e hash pelo pipeline existente.</p>}
      <Link className="ed-text-button" to="/biblioteca/skills">Revisar skill e contexto →</Link>
    </details>
  </section>
}

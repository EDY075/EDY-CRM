import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import { httpClient } from '@/services/httpClient'
import type { Connector, Operation } from './preparationTypes'
import { Badge, Erro, External, Field, Loading } from './shared'
import { date } from './domain'

const states: Record<string, string> = {nao_configurado:'Não configurado',configurado_nao_testado:'Configurado · ainda não testado',autenticacao_validada:'Autenticação validada',operacao_validada:'Operação validada',acesso_insuficiente:'Acesso insuficiente',cota_limite:'Cota / limite',expirado_ou_recusado:'Autenticação expirada ou recusada', implementacao_pendente: 'Implementação pendente', sem_credencial: 'Sem credencial', configurado_nao_validado: 'Configurado · ainda não validado', conectado: 'Conectado', limitado: 'Limitado', erro: 'Erro' }
const active = (j?: Operation) => !!j && ['na_fila', 'pesquisando'].includes(j.estado)

export function ConnectorCards() {
  const query = useQuery({ queryKey: ['ed', 'integracoes-status'], queryFn: api.integracoesStatus })
  if (query.isPending) return <Loading />
  if (query.isError) return <Erro error={query.error} />
  return <>{query.data.erro_configuracao && <div className="ed-alert error">{query.data.erro_configuracao}</div>}
    {['Criar e editar com IA','Encontrar empresas','Fotos e referências'].map(group=><section className="ed-connection-group" key={group}><h2>{group}</h2>{Object.entries(query.data.conectores).filter(([id])=>group===('openai openai_imagens voz'.split(' ').includes(id)?'Criar e editar com IA':'google firecrawl'.split(' ').includes(id)?'Encontrar empresas':'Fotos e referências')).map(([id, c]) => <details className="ed-panel ed-connection-disclosure" key={id}><summary><strong>{c.nome}</strong><span>{c.finalidade}</span><Badge tone={c.operacoes_validadas&&Object.keys(c.operacoes_validadas).length?'green':'amber'}>{c.estado==='implementacao_pendente'?'Implementação pendente':!c.credencial_presente?'Sem credencial':states[c.status_acesso||c.estado]||c.estado}</Badge></summary><ConnectorCard id={id} connector={c} /></details>)}</section>)}</>
}

export function ExtensionCards(){
  const query=useQuery({queryKey:['ed','capacidades'],queryFn:()=>httpClient.get<{id:string;nome:string;finalidade:string;configuracao:string;docs:string}[]>('/api/ed/capacidades')})
  if(query.isPending)return <Loading/>
  if(query.isError)return <Erro error={query.error}/>
  return <section className="ed-panel ed-form"><h2>Extensões futuras</h2><p>Contratos separados para versionamento, armazenamento e publicação. Nenhum envio remoto ou publicação habilitado.</p>{query.data.map(c=><details key={c.id}><summary>{c.nome} · implementação pendente</summary><p>{c.finalidade}. {c.configuracao}</p><p>Última operação: nenhuma. Consumo: não informado.</p><External url={c.docs}>Documentação oficial</External></details>)}</section>
}

function ConnectorCard({ id, connector: c }: { id: string; connector: Connector }) {
  const client = useQueryClient(), [secret, setSecret] = useState(''), [settings, setSettings] = useState(c.config), [jobId, setJobId] = useState('')
  const save = useMutation({ mutationFn: () => api.configurarIntegracao(id, { ...settings, ...(secret ? { credencial: secret } : {}) }), onSuccess: () => { setSecret(''); client.invalidateQueries({ queryKey: ['ed', 'integracoes-status'] }) } })
  const test = useMutation({ mutationFn: () => api.testarIntegracao(id), onSuccess: j => { setJobId(j.id); client.setQueryData(['ed', 'operacao', j.id], j); client.invalidateQueries({ queryKey: ['ed', 'integracoes-status'] }) } })
  const job = useQuery({ queryKey: ['ed', 'operacao', jobId], queryFn: async () => { const j = await api.operacao(jobId); if (!active(j)) client.invalidateQueries({ queryKey: ['ed', 'integracoes-status'] }); return j }, enabled: !!jobId, refetchInterval: q => active(q.state.data) ? 1200 : false })
  const cancel = useMutation({ mutationFn: () => api.cancelarOperacao(jobId), onSuccess: () => client.invalidateQueries({ queryKey: ['ed', 'operacao', jobId] }) })
  const remove=useMutation({mutationFn:()=>httpClient.put('/api/ed/integracoes/'+id,{remover_credencial:true}),onSuccess:()=>client.invalidateQueries({queryKey:['ed','integracoes-status']})})
  return <section className="ed-panel ed-form">
    <div className="ed-integration-head"><div><h2>{c.nome}</h2><p>{c.finalidade}</p></div><Badge tone={c.estado === 'conectado' ? 'green' : 'amber'}>{c.estado==='conectado'?'Autenticação validada · conferir operação':states[c.estado] || c.estado}</Badge></div>
    <p>Adaptador: {c.adaptador||'implementado'} · Autenticação: {c.autenticacao}. Conta/projeto: {c.conta_projeto||'Não informada'}.</p><p>Autenticação comprovada: {c.autenticacao_validada_em?date(c.autenticacao_validada_em):'Ainda não validada nesta configuração'}. Operações comprovadas: {Object.entries(c.operacoes_validadas||{}).map(([k,v])=>k+' · '+date(v)).join('; ')||'Nenhuma'}.</p><ul>{c.recursos.map(x => <li key={x}>{x}</li>)}</ul><p>{c.limites}</p><p><strong>Configuração necessária: </strong>{c.configuracao}</p>
    <dl className="ed-facts"><div><dt>Credencial</dt><dd>{c.credencial_presente ? 'Presente no backend · valor protegido' : 'Não informada'}</dd></div><div><dt>Última execução validada nesta configuração</dt><dd>{c.ultima_execucao ? date(c.ultima_execucao) : 'Nenhuma'}</dd></div><div><dt>Consumo / saldo informado</dt><dd>{c.consumo && Object.keys(c.consumo).length ? Object.entries(c.consumo).map(([k, v]) => `${k}: ${v}`).join(' · ') : 'Fornecedor não informou nesta execução; não é uma estimativa de custo.'}</dd></div></dl>
    {c.mensagem && <p role="status">{c.mensagem}</p>}{c.implementacao_pendente.map(x => <p key={x}><Badge tone="amber">Implementação pendente</Badge> {x}</p>)}
    <details><summary>Configurar {c.nome}</summary><form onSubmit={e => { e.preventDefault(); save.mutate() }}>
      <Field label={`Nova credencial · ${c.nome}`} hint="Nunca exibida novamente. Windows: cofre DPAPI no projeto. Variáveis do processo têm prioridade; não são alteradas por este formulário."><input type="password" autoComplete="new-password" maxLength={4000} value={secret} onChange={e => setSecret(e.target.value)} placeholder="Deixe vazio para preservar a credencial" /></Field>
      {['openai','openai_imagens','voz'].includes(id) && <Field label={`ID do modelo · ${c.nome}`}><input maxLength={100} value={settings.modelo || ''} onChange={e => setSettings({ ...settings, modelo: e.target.value })} placeholder={id==='voz'?'gpt-transcribe':id==='openai_imagens'?'gpt-image-2.5-sunburst':'ID disponível no painel API'} /></Field>}
      {['instagram','meta_discovery'].includes(id) && <><Field label={`ID da conta profissional · ${c.nome}`}><input maxLength={100} value={settings.account_id || ''} onChange={e => setSettings({ ...settings, account_id: e.target.value })} /></Field><Field label={`Versão da API Meta · ${c.nome}`}><input maxLength={100} value={settings.api_version || ''} onChange={e => setSettings({ ...settings, api_version: e.target.value })} placeholder="Versão suportada pelo painel Meta" /></Field></>}
      <button className="ed-button" disabled={save.isPending || active(job.data)}>Salvar configuração</button>{save.isError && <Erro error={save.error} />}{save.isSuccess && <p className="ed-success" role="status">Configuração salva. Execute o teste para validar o acesso.</p>}
    </form></details>
    <small>Teste de Google faz uma chamada de IDs e pode consumir cota. Firecrawl consulta créditos; OpenAI consulta modelos; Meta lê a conta autorizada. O teste não garante todos os recursos nem libera direitos de exportação.</small>
    <button className="ed-button" disabled={!c.credencial_presente || test.isPending || active(job.data) || save.isPending || !!secret} onClick={() => test.mutate()}>{active(job.data) ? 'Testando…' : 'Testar conexão'}</button>
    <button className="ed-button" disabled={!c.credencial_presente||save.isPending||remove.isPending||active(job.data)} onClick={()=>remove.mutate()}>Remover credencial local</button>{remove.isError&&<Erro error={remove.error}/>}<small>Uma variável de ambiente presente continua ativa; remover o cache local não altera o ambiente do processo.</small>
    {test.isError && <Erro error={test.error} />}{job.isError && <Erro error={job.error} />}{cancel.isError && <Erro error={cancel.error} />}
    {job.data && <div role="status"><p>{job.data.mensagem}</p><progress aria-label={`Progresso de ${c.nome}`} max={100} value={job.data.progresso} />{active(job.data) && <button className="ed-button" disabled={cancel.isPending} onClick={() => cancel.mutate()}>Cancelar teste</button>}</div>}
    <External url={c.docs}>Documentação oficial</External>
  </section>
}

import {FileInput} from './shared'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from './api'
import { Badge, Erro, External, Field, Loading } from './shared'
import type { Empresa } from './types'
import type { Operation, Preparation } from './preparationTypes'
import { PreparationImages } from './PreparationImages'

const labels: Record<string, string> = { objetivo: 'Objetivo', publico: 'Público', oferta: 'Oferta confirmada / a validar', cta: 'Chamada principal (CTA)',
  funcionalidades: 'Funcionalidades e fluxos', banco: 'Banco de dados e entidades', administracao: 'Administração, papéis e autenticação',
  paleta: 'Paleta · cores em HEX', fonte_titulos: 'Fonte de títulos', fonte_texto: 'Fonte de texto', estilo: 'Estilo e identidade', composicao: 'Composição', movimento: 'Movimento geral', shader: 'Shaders · atmosfera do nicho', titulos: 'Animação de título e subtítulo', cursor: 'Efeito no cursor · partículas do nicho', restricoes: 'Limites e acessibilidade' }
const active = (job?: Operation) => !!job && ['na_fila', 'pesquisando'].includes(job.estado)

export function PreparacaoPanel({ empresa }: { empresa: Empresa }) {
  const query = useQuery({ queryKey: ['ed', 'preparacao', empresa.id], queryFn: () => api.preparacao(empresa.id) })
  if (query.isPending) return <Loading />
  if (query.isError) return <Erro error={query.error} />
  return <PreparationEditor empresa={empresa} initial={query.data} />
}

function PreparationEditor({ empresa, initial }: { empresa: Empresa; initial: Preparation }) {
  const client = useQueryClient(), [p, setP] = useState(initial), [dirty, setDirty] = useState(false), [jobId, setJobId] = useState('')
  const change = (next: Preparation) => { setP(next); setDirty(true) }
  const save = useMutation({ mutationFn: () => api.salvarPreparacao(empresa.id, p), onSuccess: async next => { setP(next); setDirty(false); await client.invalidateQueries({ queryKey: ['ed'] }) } })
  const pending = useQuery({ queryKey: ['ed', 'preparacao-pendencias', empresa.id], queryFn: () => api.pendenciasPreparacao(empresa.id) })
  const connectors = useQuery({ queryKey: ['ed', 'integracoes-status'], queryFn: api.integracoesStatus })
  const operation = useQuery({ queryKey: ['ed', 'operacao', jobId], queryFn: () => api.operacao(jobId), enabled: !!jobId, refetchInterval: q => active(q.state.data) ? 1200 : false })
  const generate = useMutation({ mutationFn: () => api.gerarTexto(empresa.id, p.revisao), onSuccess: j => { setJobId(j.id); client.setQueryData(['ed', 'operacao', j.id], j) } })
  const cancel = useMutation({ mutationFn: () => api.cancelarOperacao(jobId), onSuccess: () => client.invalidateQueries({ queryKey: ['ed', 'operacao', jobId] }) })
  const [refUrl, setRefUrl] = useState(''), [refNote, setRefNote] = useState('')
  const upload = useMutation({ mutationFn: async (file: File) => { const form = new FormData(); form.set('arquivo', file); form.set('categoria', 'referencia_design'); form.set('origem', 'Upload de referência visual pelo usuário'); return api.upload(empresa.id, form) },
    onSuccess: m => { change({ ...p, referencias: [...p.referencias, { url: '', material_id: m.id, observacao: 'Referência visual enviada; autorização de exportação pendente na galeria.' }] }); client.invalidateQueries({ queryKey: ['ed', 'empresa', empresa.id] }) } })
  const template = `Olá! Preparei uma proposta de organização das informações públicas de ${empresa.nome} em uma landing page. Posso compartilhar a prévia para vocês avaliarem a identidade visual e os canais de contato? Informações e materiais serão revisados com a empresa antes de publicação.`
  return <div className="ed-preparation">
    <div className="ed-prep-toolbar"><div><strong>Preparar projeto para o Codex</strong><small>{dirty ? 'Edições não salvas — salve antes de trocar de aba ou exportar.' : `Revisão ${p.revisao} · decisões preservadas`}</small></div><button className="ed-button primary" disabled={save.isPending || !dirty} onClick={() => save.mutate()}>{save.isPending ? 'Salvando…' : 'Salvar preparação'}</button></div>
    {save.isError && <Erro error={save.error} />}{save.isSuccess && !dirty && <p className="ed-success" role="status">Preparação salva. O próximo ZIP usará esta revisão.</p>}
    <fieldset className="ed-prep-fieldset" disabled={save.isPending}>
      <section className="ed-panel ed-form"><h2>Escopo e intenção</h2><p>Fatos comerciais ficam na ficha. Aqui você define o projeto e revisa propostas de texto; os temas do CRM não determinam o visual da página.</p>
        <Field label="Tipo de entrega"><select value={p.modo} onChange={e => change({ ...p, modo: e.target.value })}><option value="previa">Prévia de landing page · prospecção</option><option value="completo">Site completo · funcionalidades, banco e administração</option></select></Field>
        <div className="ed-form-grid">{(['objetivo', 'publico', 'oferta', 'cta'] as const).map(k => <Field key={k} label={labels[k]}><textarea maxLength={4000} rows={3} value={p[k]} onChange={e => change({ ...p, [k]: e.target.value })} /></Field>)}</div>
        {p.modo === 'completo' && <><p>O Codex construirá o site conforme os requisitos revisados. Este modo não copia o banco do CRM nem publica automaticamente.</p>{(['funcionalidades', 'banco', 'administracao'] as const).map(k => <Field key={k} label={labels[k]}><textarea maxLength={4000} rows={3} value={p[k]} onChange={e => change({ ...p, [k]: e.target.value })} /></Field>)}</>}
      </section>
      <section className="ed-panel ed-form"><h2>Direção visual e efeitos</h2><p>Defina uma identidade específica para o nicho. Efeitos são requisitos para o projeto externo; esta tela não gera a landing page.</p>
        <div className="ed-palette" aria-label="Prévia da paleta">{(p.design.paleta.match(/#[0-9a-fA-F]{6}\b/g) || []).slice(0, 10).map((c, i) => <span key={`${c}-${i}`} style={{ backgroundColor: c }} title={c}><span>{c}</span></span>)}</div>
        <div className="ed-form-grid">{Object.entries(p.design).map(([k, v]) => <Field key={k} label={labels[k] || k}><textarea value={v} rows={3} maxLength={2000} onChange={e => change({ ...p, design: { ...p.design, [k]: e.target.value } })} /></Field>)}</div>
      </section>
      <section className="ed-panel ed-form"><h2>Referências e observações</h2><p>URLs são referências externas, sem permissão automática para reutilizar fotos. Uploads aparecem na galeria para autorizar e selecionar.</p>
        <Field label="URL de referência"><input type="url" value={refUrl} maxLength={2000} onChange={e => setRefUrl(e.target.value)} placeholder="https://…" /></Field><Field label="O que aproveitar da referência"><textarea value={refNote} maxLength={2000} onChange={e => setRefNote(e.target.value)} placeholder="Hierarquia, composição, movimento; preservar identidade própria" /></Field>
        <button type="button" className="ed-button" disabled={!/^https?:\/\//.test(refUrl) || p.referencias.length >= 30} onClick={() => { change({ ...p, referencias: [...p.referencias, { url: refUrl, material_id: '', observacao: refNote }] }); setRefUrl(''); setRefNote('') }}>Adicionar referência</button>
        <Field label="Upload de imagem de referência"><FileInput accept="image/png,image/jpeg,image/webp" disabled={upload.isPending} onChange={e => { if (e.target.files?.[0]) upload.mutate(e.target.files[0]); e.target.value = '' }} /></Field>
        {upload.isError && <Erro error={upload.error} />}
        {p.referencias.map((r, i) => <div key={i} className="ed-reference">{r.url && <External url={r.url}>{r.url}</External>}{r.material_id && <p>Imagem: {empresa.materiais.find(m => m.id === r.material_id)?.nome_original || 'Upload na galeria'}</p>}
          <Field label={`Observação da referência ${i + 1}`}><textarea maxLength={2000} value={r.observacao} onChange={e => change({ ...p, referencias: p.referencias.map((x, n) => n === i ? { ...x, observacao: e.target.value } : x) })} /></Field>
          <button type="button" className="ed-button" onClick={() => change({ ...p, referencias: p.referencias.filter((_, n) => n !== i) })}>Remover referência {i + 1}</button></div>)}
      </section>
      <PreparationImages empresa={empresa} images={p.imagens} onChange={imagens => change({ ...p, imagens })} />
      <section className="ed-panel ed-form"><h2>Estrutura e texto por seção</h2><p>Texto é uma proposta editorial. Revise sua correspondência com os fatos confirmados antes de aprovar.</p>
        {p.secoes.map((s, i) => <article className="ed-prep-section" key={s.id}><Badge tone={s.revisado ? 'green' : 'amber'}>{s.revisado ? 'Texto revisado' : 'Sugestão para revisar'}</Badge>
          <Field label={`Título · ${s.id}`}><input maxLength={300} value={s.titulo} onChange={e => change({ ...p, secoes: p.secoes.map((x, n) => n === i ? { ...x, titulo: e.target.value, revisado: false } : x) })} /></Field>
          <Field label={`Texto · ${s.id}`}><textarea maxLength={4000} rows={4} value={s.texto} onChange={e => change({ ...p, secoes: p.secoes.map((x, n) => n === i ? { ...x, texto: e.target.value, revisado: false } : x) })} /></Field>
          <label className="ed-check"><input type="checkbox" checked={s.revisado} onChange={e => change({ ...p, secoes: p.secoes.map((x, n) => n === i ? { ...x, revisado: e.target.checked } : x) })} /> Revisei o texto e os fatos desta seção.</label>
          <div className="ed-actions"><button className="ed-button" type="button" disabled={i === 0} onClick={() => { const list = [...p.secoes]; [list[i - 1], list[i]] = [list[i], list[i - 1]]; change({ ...p, secoes: list }) }}>Mover acima</button><button className="ed-button" type="button" onClick={() => change({ ...p, secoes: p.secoes.filter((_, n) => i !== n) })}>Remover seção</button></div>
        </article>)}
        <button className="ed-button" type="button" disabled={p.secoes.length >= 30} onClick={() => change({ ...p, secoes: [...p.secoes, { id: `secao-${Date.now()}`, titulo: 'Nova seção', texto: '', revisado: false }] })}>Adicionar seção</button>
        <Field label="Texto de prospecção · rascunho para revisão"><textarea maxLength={4000} rows={4} value={p.prospeccao} onChange={e => change({ ...p, prospeccao: e.target.value })} /></Field>
        <details><summary>Ver template de prospecção sem IA</summary><p>{template}</p><button type="button" className="ed-button" onClick={() => change({ ...p, prospeccao: template })}>Usar este rascunho na edição</button></details>
      </section>
    </fieldset>
    <section className="ed-panel ed-form"><h2>IA opcional · propostas separadas</h2><p>Salve a preparação antes de gerar. Envia à OpenAI os fatos confirmados e objetivo, público, oferta e CTA. Não envia imagens nem credenciais do CRM.</p>
      <button className="ed-button" disabled={dirty || generate.isPending || active(operation.data) || !connectors.data?.conectores.openai.credencial_presente} onClick={() => generate.mutate()}>Gerar proposta de texto com OpenAI</button><Link className="ed-back" to="/integracoes">Configurar integrações</Link>
      {generate.isError && <Erro error={generate.error} />}{operation.isError && <Erro error={operation.error} />}
      {operation.data && <div role="status"><p>{operation.data.mensagem}</p><progress max={100} value={operation.data.progresso} aria-label="Progresso da IA" />{active(operation.data) && <button className="ed-button" disabled={cancel.isPending} onClick={() => cancel.mutate()}>Cancelar geração</button>}</div>}
      {cancel.isError && <Erro error={cancel.error} />}
      {operation.data?.proposta && <><p className="ed-alert">Proposta não confirma fatos. Compare com suas edições; substituições dependem da sua escolha. {operation.data.revisao !== p.revisao && 'Preparação mudou: gere novamente antes de aplicar.'}</p>
        <dl><dt>Prospecção atual</dt><dd>{p.prospeccao || 'Em branco'}</dd><dt>Proposta de prospecção</dt><dd>{operation.data.proposta.prospeccao}</dd></dl><button className="ed-button" disabled={operation.data.revisao !== p.revisao} onClick={() => change({ ...p, prospeccao: operation.data!.proposta!.prospeccao })}>Usar proposta de prospecção na edição</button>
        {operation.data.proposta.secoes.map(s => <article key={s.id} className="ed-prep-section"><h3>{s.id}</h3><p>Atual: {p.secoes.find(x => x.id === s.id)?.texto}</p><p>Proposta: {s.titulo} — {s.texto}</p><button className="ed-button" disabled={operation.data?.revisao !== p.revisao} onClick={() => change({ ...p, secoes: p.secoes.map(x => x.id === s.id ? { ...s, revisado: false } : x) })}>Usar proposta em {s.id}</button></article>)}</>}
    </section>
    <section className="ed-panel ed-form"><h2>Fatos confirmados e pendências</h2><dl className="ed-facts">{Object.entries(empresa.fontes).filter(([, s]) => s.verificacao === 'confirmado_usuario').map(([k, s]) => <div key={k}><dt>{k}</dt><dd>{s.valor}</dd></div>)}</dl>
      <p>Pendências calculadas a partir da última revisão salva:</p>{pending.isError ? <Erro error={pending.error} /> : <ul>{pending.data?.map(x => <li key={x}>{x}</li>)}</ul>}<small>Depois de salvar, abra Documento e exportação para gerar o pacote completo. A criação e o refinamento acontecem no Codex.</small></section>
    <button className="ed-button primary" disabled={save.isPending || !dirty} onClick={() => save.mutate()}>Salvar preparação</button>
  </div>
}

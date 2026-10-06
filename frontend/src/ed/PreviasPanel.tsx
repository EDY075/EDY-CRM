import { useState } from 'react'
import {Link} from 'react-router-dom'
import {RefinePreviewButton} from './PreviewActions'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link2 } from 'lucide-react'
import { api } from './api'
import type { Empresa } from './types'
import { Badge, Empty, Erro, External, Field } from './shared'
import { date } from './domain'

export function PreviasPanel({ empresa, onReopen: _onReopen }: { empresa: Empresa; onReopen: () => void }) {
  const client = useQueryClient()
  const [url, setUrl] = useState(''), [notes, setNotes] = useState('')
  const [version, setVersion] = useState(empresa.exportacoes[0]?.id || '')
  const mutation = useMutation({ mutationFn: () => api.previa(empresa.id, { url, exportacao_id: version, observacoes: notes }),
    onSuccess: async () => { setUrl(''); setNotes(''); await client.invalidateQueries({ queryKey: ['ed'] }) } })
  return <>
    <div className="ed-section-title"><h2>Prévia criada no Codex</h2><p>Registre o resultado manualmente e relacione-o ao pacote que você usou.</p></div>
    {empresa.exportacoes.length ? <form className="ed-panel ed-form" onSubmit={e => { e.preventDefault(); mutation.mutate() }}>
      <Field label="Link da prévia"><input type="url" required maxLength={2000} placeholder="https://…" value={url} onChange={e => setUrl(e.target.value)} /></Field>
      <Field label="Pacote utilizado"><select value={version} required onChange={e => setVersion(e.target.value)}>{empresa.exportacoes.map(x => <option key={x.id} value={x.id}>Versão {x.versao} · {date(x.criado_em)}</option>)}</select></Field>
      <Field label="Observações sobre a prévia"><textarea rows={3} maxLength={2000} value={notes} onChange={e => setNotes(e.target.value)} /></Field>
      <button className="ed-button primary" disabled={mutation.isPending}><Link2 size={16} />{mutation.isPending ? 'Registrando…' : 'Registrar prévia'}</button>
      {mutation.isError && <Erro error={mutation.error} />}{mutation.isSuccess && <p role="status" className="ed-success">Prévia registrada.</p>}
    </form> : <div className="ed-panel"><Empty title="Exporte o primeiro pacote">Depois de criar a landing page no Codex, volte aqui para adicionar o link.</Empty></div>}
    {empresa.previas.length > 0 && <div className="ed-preview-list">{empresa.previas.map(x => <article className="ed-panel ed-form" key={x.id}><Badge tone={x.construcao_id&&!x.url_ativa?'amber':'green'}>{x.construcao_id&&!x.url_ativa?'Prévia registrada · servidor parado':'Prévia registrada'}</Badge>{x.construcao_id?<div className="ed-actions"><Link className="ed-button primary" to={`/previas/${empresa.id}/${x.construcao_id}`}>Abrir esta versão</Link><RefinePreviewButton company={empresa.id} build={x.construcao_id}/></div>:<h3><External url={x.url}>{x.url}</External></h3>}<p>{x.observacoes || 'Sem observações.'}</p><small>Versão {empresa.exportacoes.find(e => e.id === x.exportacao_id)?.versao} · {date(x.criado_em)}</small></article>)}</div>}
  </>
}

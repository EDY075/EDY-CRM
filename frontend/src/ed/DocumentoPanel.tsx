import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, FileText, Save, PackageCheck } from 'lucide-react'
import { api } from './api'
import type { Briefing, Documento, Empresa, Exportacao } from './types'
import { Badge, Erro, Field, Loading } from './shared'
import { date } from './domain'

const labels: Record<keyof Briefing, string> = {
  diagnostico: 'Relatório / diagnóstico observado', objetivo: 'Objetivo da landing page', publico: 'Público proposto',
  cta: 'Chamada para ação', secoes: 'Estrutura de seções', direcao: 'Direção visual', complemento: 'Complemento do documento',
}
function Editor({ empresa, documento }: { empresa: Empresa; documento: Documento }) {
  const client = useQueryClient()
  const [draft, setDraft] = useState(documento.briefing)
  const [exported, setExported] = useState<Exportacao>()
  const [saved, setSaved] = useState(false)
  const save = useMutation({ mutationFn: () => api.salvar(empresa.id, { briefing: draft,
    etapa: ['exportado_codex', 'previa_pronta'].includes(empresa.etapa) ? empresa.etapa : 'documento_pronto' }),
    onSuccess: async () => { setSaved(true); await client.invalidateQueries({ queryKey: ['ed'] }) } })
  const exportMutation = useMutation({ mutationFn: async () => {
    await api.salvar(empresa.id, { briefing: draft }); return api.exportar(empresa.id)
  }, onSuccess: async data => { setExported(data); setSaved(true); await client.invalidateQueries({ queryKey: ['ed'] }) } })
  const busy = save.isPending || exportMutation.isPending
  return <>
    <form className="ed-panel ed-form" onSubmit={e => { e.preventDefault(); save.mutate() }}>
      <div className="ed-section-title"><h2>Relatório e briefing</h2><p>Relatório e briefing básico preservados. A aba Preparar prévia define escopo, oferta, direção visual, recortes e textos do novo pacote; seus campos salvos têm prioridade.</p></div>
      <div className="ed-form-grid">{Object.entries(labels).map(([key, label]) => <Field key={key} label={label} hint={key === 'diagnostico' ? 'Registre apenas problemas observados, sem notas ou medições inventadas.' : undefined}>
        <textarea rows={key === 'complemento' ? 5 : 3} maxLength={key === 'complemento' ? 12000 : 4000}
          value={draft[key as keyof Briefing]} onChange={e => { setSaved(false); setDraft({ ...draft, [key]: e.target.value }) }} />
      </Field>)}</div>
      <button className="ed-button" disabled={busy}><Save size={16} />{save.isPending ? 'Salvando…' : 'Salvar briefing'}</button>
      {save.isError && <Erro error={save.error} />}{saved && <p className="ed-success" role="status">Briefing salvo.</p>}
    </form>
    <section className="ed-export-panel"><div><span className="ed-eyebrow">PRONTO PARA O PRÓXIMO PASSO</span><h2>Um pacote. Todo o contexto.</h2><p>empresa.md, briefing.md, DESIGN.md, referencias.md, materiais.json, prompt-codex.md, LEIA-ME.md e {empresa.materiais.filter(x => x.selecionado && x.autorizado).length} imagens selecionadas. As pendências seguem explícitas no documento.</p><small>O botão salva o briefing atual e cria uma versão independente do banco local.</small></div>
      <button className="ed-button primary" disabled={busy} onClick={() => exportMutation.mutate()}><Download size={18} />{exportMutation.isPending ? 'Preparando pacote…' : 'Exportar para o Codex'}</button>
    </section>
    {exportMutation.isError && <Erro error={exportMutation.error} />}
    {exported && <div className="ed-downloads" role="status"><PackageCheck size={22} /><div><strong>Versão {exported.versao} pronta</strong><p>Baixe o ZIP ou o documento Markdown e entregue os materiais ao Codex.</p></div><a className="ed-button primary" href={exported.zip_url} download><Download size={16} /> Baixar ZIP</a><a className="ed-button" href={exported.markdown_url} download><FileText size={16} /> Baixar Markdown</a></div>}
    <details className="ed-panel ed-doc-preview"><summary>Ver documento completo e prompt</summary><p className="ed-muted">Exibe a última versão salva do briefing. Cada exportação mantém sua própria cópia.</p><textarea aria-label="Documento Markdown completo" readOnly value={documento.markdown + "\n\n" + documento.prompt} rows={22} /></details>
    {empresa.exportacoes.length > 0 && <section className="ed-panel ed-form"><h2>Histórico de pacotes</h2><div className="ed-history">{empresa.exportacoes.map(x => <div key={x.id}><span><Badge>Versão {x.versao}</Badge> {date(x.criado_em)}</span><span><a href={x.zip_url} download>ZIP <Download size={14} /></a><a href={x.markdown_url} download>Markdown <FileText size={14} /></a></span></div>)}</div></section>}
  </>
}
export function DocumentoPanel({ empresa }: { empresa: Empresa }) {
  const query = useQuery({ queryKey: ['ed', 'documento', empresa.id], queryFn: () => api.documento(empresa.id) })
  return query.isPending ? <Loading /> : query.isError ? <Erro error={query.error} /> : <Editor empresa={empresa} documento={query.data} />
}

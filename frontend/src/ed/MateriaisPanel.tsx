import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ImagePlus, Upload, Check, Save } from 'lucide-react'
import { api } from './api'
import type { Empresa, Material } from './types'
import { Badge, Erro, Field, FileInput } from './shared'

function MaterialCard({ empresaId, material }: { empresaId: string; material: Material }) {
  const client = useQueryClient()
  const [selected, setSelected] = useState(material.selecionado)
  useEffect(() => setSelected(material.selecionado), [material.selecionado])
  const [draft, setDraft] = useState({ origem: material.origem, atribuicao: material.atribuicao,
    posicao: material.posicao, categoria: material.categoria, autorizado: material.autorizado })
  const mutation = useMutation({ mutationFn: (data: Partial<Material>) => api.material(empresaId, material.id, data),
    onSuccess: () => client.invalidateQueries({ queryKey: ['ed'] }) })
  return <article className="ed-material">
    <img src={material.arquivo_url} alt={`Material enviado: ${material.nome_original}`} loading="lazy" />
    <div className="ed-material-body"><strong>{material.nome_original}</strong><span className="ed-muted">{material.categoria} · conteúdo a conferir</span>
      <Badge tone={material.autorizado ? 'green' : 'amber'}>{material.autorizado ? 'Uso confirmado por você' : 'Referência interna'}</Badge>
      <label className="ed-check"><input type="checkbox" checked={selected} disabled={!material.autorizado || mutation.isPending}
        onChange={e => { setSelected(e.target.checked); mutation.mutate({ selecionado: e.target.checked }, { onError: () => setSelected(material.selecionado) }) }} /> Incluir no pacote</label>
      <details><summary>Origem e autorização</summary><form onSubmit={e => { e.preventDefault(); mutation.mutate({ ...draft, selecionado: draft.autorizado ? material.selecionado : false }) }}>
        <Field label="Origem do material"><input required={draft.autorizado} maxLength={1000} value={draft.origem} onChange={e => setDraft({ ...draft, origem: e.target.value })} /></Field>
        <Field label="Atribuição / titular"><input required={draft.autorizado} maxLength={1000} value={draft.atribuicao} onChange={e => setDraft({ ...draft, atribuicao: e.target.value })} /></Field>
        <Field label="Categoria sugerida"><input maxLength={1000} value={draft.categoria} onChange={e => setDraft({ ...draft, categoria: e.target.value })} /></Field>
        <Field label="Posição sugerida na página"><input maxLength={1000} value={draft.posicao} onChange={e => setDraft({ ...draft, posicao: e.target.value })} /></Field>
        <label className="ed-check"><input type="checkbox" checked={draft.autorizado} onChange={e => setDraft({ ...draft, autorizado: e.target.checked })} /> Confirmo que posso exportar e usar este material.</label>
        <button className="ed-button" disabled={mutation.isPending}><Save size={14} /> Salvar material</button>
      </form></details>
      {mutation.isError && <Erro error={mutation.error} />}
    </div>
  </article>
}

export function MateriaisPanel({ empresa }: { empresa: Empresa }) {
  const client = useQueryClient()
  const [formKey, setFormKey] = useState(0)
  const mutation = useMutation({ mutationFn: (data: FormData) => api.upload(empresa.id, data),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ['ed'] }); setFormKey(x => x + 1) } })
  return <>
    <div className="ed-section-title"><h2>Materiais visuais</h2><p>Selecione os arquivos que acompanharão o documento. Categorias são sugestões a conferir.</p></div>
    <div className="ed-alert"><ImagePlus size={18} /><span>Acesso público não confirma autorização. Imagens sem uso confirmado ficam como referência interna.</span></div>
    {empresa.materiais.length > 0 && <div className="ed-gallery">{empresa.materiais.map(m => <MaterialCard key={m.id} empresaId={empresa.id} material={m} />)}</div>}
    <form key={formKey} className="ed-panel ed-form" onSubmit={e => {
      e.preventDefault(); const data = new FormData(e.currentTarget)
      data.set('autorizado', data.get('autorizado') ? 'true' : 'false'); mutation.mutate(data)
    }}>
      <div className="ed-section-title"><h3>Adicionar imagem</h3><p>PNG, JPEG ou WebP · até 8 MB e 24 megapixels · até 30 arquivos por empresa.</p></div>
      <Field label="Arquivo"><FileInput name="arquivo" accept="image/png,image/jpeg,image/webp" required /></Field>
      <Field label="Natureza do original"><select name="natureza"><option value="a_confirmar">A confirmar</option><option value="fotografia_original">Fotografia original</option><option value="ilustracao">Ilustração · não representa registro real</option><option value="logo">Logo oficial · conferir identidade</option><option value="referencia">Referência visual</option></select></Field>
      <div className="ed-form-grid"><Field label="Origem"><input name="origem" maxLength={1000} placeholder="URL de origem ou material enviado pelo cliente" /></Field><Field label="Atribuição / titular"><input name="atribuicao" maxLength={1000} placeholder="Quem produziu ou forneceu o arquivo" /></Field>
        <Field label="Categoria sugerida"><select name="categoria"><option value="referencia">Referência (a conferir)</option><option value="logo">Logo</option><option value="fachada">Fachada</option><option value="ambiente">Ambiente</option><option value="equipe">Equipe (confirmar pessoas)</option><option value="produto">Produto / serviço</option></select></Field>
        <Field label="Posição sugerida"><input name="posicao" maxLength={500} placeholder="Ex.: hero ou galeria; confirmar conteúdo" /></Field></div>
      <label className="ed-check"><input type="checkbox" name="autorizado" /> Confirmo que posso exportar e usar esta imagem; informei sua origem e atribuição.</label>
      {mutation.isError && <Erro error={mutation.error} />}{mutation.isSuccess && <p className="ed-success" role="status"><Check size={16} /> Imagem adicionada. Selecione-a na galeria para incluir no pacote.</p>}
      <button className="ed-button primary" disabled={mutation.isPending}><Upload size={16} />{mutation.isPending ? 'Enviando…' : 'Enviar imagem'}</button>
    </form>
  </>
}

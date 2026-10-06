import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Save } from 'lucide-react'
import { api } from './api'
import type { Empresa } from './types'
import { Erro, Field } from './shared'

const fields = [
  ['nome', 'Nome público da empresa', 'text'], ['nicho', 'Nicho / categoria', 'text'],
  ['cidade', 'Cidade', 'text'], ['uf', 'UF', 'text'], ['bairro', 'Bairro', 'text'],
  ['endereco', 'Endereço do estabelecimento', 'text'], ['telefone', 'Contato comercial', 'text'],
  ['email', 'E-mail comercial', 'text'],
  ['site', 'Site', 'url'], ['instagram', 'URL do Instagram', 'url'],
  ['horarios', 'Horários de funcionamento', 'text'], ['fonte_url', 'URL da fonte da informação', 'url'],
  ['fonte_busca_url', 'Link de busca / referência (fonte)', 'url'], ['fonte_mapa_url', 'Link de mapa / localização (fonte)', 'url'],
] as const
type FormValues = Record<typeof fields[number][0] | 'servicos' | 'observacoes' | 'descricao' | 'redes_sociais', string>

export function EmpresaForm({ empresa, onSaved }: { empresa?: Empresa; onSaved?: () => void }) {
  const navigate = useNavigate(), client = useQueryClient()
  const [values, setValues] = useState<FormValues>(() => Object.fromEntries(
    [...fields.map(([key]) => [key, empresa?.[key] || '']), ['servicos', empresa?.servicos || ''],
      ['observacoes', empresa?.observacoes || ''], ['descricao', empresa?.descricao || ''], ['redes_sociais', empresa?.redes_sociais || '']]) as FormValues)
  const [confirmed, setConfirmed] = useState(empresa?.confirmado || false)
  const [demo, setDemo] = useState(empresa?.demonstracao || false)
  const [saved, setSaved] = useState(false)
  const mutation = useMutation({ mutationFn: () => empresa ? api.salvar(empresa.id, { ...values, confirmado: confirmed, demonstracao: demo })
    : api.criar({ ...values, confirmado: confirmed, demonstracao: demo }),
    onSuccess: async data => {
      await client.invalidateQueries({ queryKey: ['ed'] }); setSaved(true)
      if (onSaved) onSaved(); else navigate(`/empresas/${data.id}`)
    } })
  return <form className="ed-form ed-panel" onSubmit={e => { e.preventDefault(); setSaved(false); mutation.mutate() }}>
    <div className="ed-section-title"><h2>Informações da empresa</h2><p>Deixe em branco o que ainda precisa pesquisar. Links genéricos de buscadores e pesquisas/mapas são guardados como fontes. Uma URL específica, inclusive Google Sites, entra como candidata; confirme a associação separadamente na ficha.</p></div>
    <div className="ed-form-grid">{fields.map(([key, label, type]) => <Field key={key} label={label}>
      <input type={type} required={key === 'nome'} maxLength={key === 'uf' ? 2 : 500} value={values[key]}
        placeholder={type === 'url' ? 'https://…' : ''} onChange={e => setValues({ ...values, [key]: e.target.value })} />
    </Field>)}</div>
    <Field label="Serviços confirmados" hint="Não deduza serviços apenas pela categoria da empresa."><textarea maxLength={4000} rows={3} value={values.servicos} onChange={e => setValues({ ...values, servicos: e.target.value })} /></Field>
    <Field label="Descrição comercial"><textarea maxLength={4000} rows={3} value={values.descricao} onChange={e => setValues({ ...values, descricao: e.target.value })} /></Field>
    <Field label="Links sociais"><textarea maxLength={4000} rows={2} value={values.redes_sociais} onChange={e => setValues({ ...values, redes_sociais: e.target.value })} /></Field>
    <Field label="Notas internas" hint="Observações de pesquisa; não são exportadas como fatos da empresa."><textarea maxLength={4000} rows={3} value={values.observacoes} onChange={e => setValues({ ...values, observacoes: e.target.value })} /></Field>
    <label className="ed-check"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> Conferi a identidade e as informações preenchidas com a empresa.</label>
    <label className="ed-check"><input type="checkbox" checked={demo} onChange={e => setDemo(e.target.checked)} /> Estes são dados de demonstração de uma empresa fictícia.</label>
    {mutation.isError && <Erro error={mutation.error} />}{saved && <p className="ed-success" role="status">Informações salvas.</p>}
    <div className="ed-form-actions"><button className="ed-button primary" disabled={mutation.isPending}><Save size={16} />{mutation.isPending ? 'Salvando…' : 'Salvar empresa'}</button></div>
  </form>
}

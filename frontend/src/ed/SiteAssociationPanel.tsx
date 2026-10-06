import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import type { Empresa } from './types'
import { Badge, Erro, External, Field } from './shared'
import { date } from './domain'

const fields: Record<string, string> = { nome: 'Nome', localizacao: 'Localização', contato: 'Contato', vinculo_social: 'Vínculo social', revisao_usuario: 'Revisão humana' }

export function SiteAssociationPanel({ empresa, onEdit, onMaterials }: { empresa: Empresa; onEdit: () => void; onMaterials: () => void }) {
  const client = useQueryClient()
  const [note, setNote] = useState(''), [reviewed, setReviewed] = useState(false)
  const query = useQuery({ queryKey: ['ed', 'site-associacao', empresa.id], queryFn: () => api.associacaoSite(empresa.id) })
  const verify = useMutation({ mutationFn: () => api.verificarSite(empresa.id, empresa.site), onSuccess: () => client.invalidateQueries({ queryKey: ['ed', 'site-associacao', empresa.id] }) })
  const confirm = useMutation({ mutationFn: () => api.confirmarSite(empresa.id, empresa.site, note), onSuccess: async () => {
    setReviewed(false); setNote(''); await client.invalidateQueries({ queryKey: ['ed'] })
  } })
  const association = empresa.associacao_site
  const proposal = query.data?.proposta
  return <section className="ed-panel ed-form ed-site-association" aria-label="Associação do site">
    <div className="ed-section-title"><h2>Associação do site</h2><p>Uma URL disponível não comprova vínculo com a empresa. Confira evidências, identidade e filial antes de usar como site oficial.</p></div>
    <Badge tone={association.estado === 'confirmado' ? 'green' : 'amber'}>{association.estado === 'confirmado' ? 'Site confirmado por revisão humana' : empresa.site ? 'Site candidato · associação pendente' : 'Sem site confirmado · associação pendente'}</Badge>
    <p>{empresa.site ? <External url={empresa.site}>{empresa.site}</External> : 'Nenhum endereço substituto foi deduzido.'}</p>
    <small>{association.motivo}</small>
    {association.evidencias.map((e,i) => <p key={i}>{fields[e.campo] || e.campo}: {e.evidencia} · <External url={e.origem}>Origem</External></p>)}
    {!!empresa.site && <>
      <button className="ed-button" disabled={verify.isPending} onClick={() => verify.mutate()}>{verify.isPending ? 'Conferindo robots.txt e uma página…' : 'Verificar evidências de associação'}</button>
      <small>Leitura local de uma página, sem executar JavaScript ou aplicar informações; respeita robots.txt. Correspondências continuam sendo sugestões.</small>
      {proposal && <div className="ed-site-evidence" role="status"><p><strong>{proposal.ambiguo ? 'Associação ambígua · revisão necessária' : 'Correspondências encontradas · revisão necessária'}</strong><br />{proposal.mensagem} · {date(proposal.consultado_em)}</p>
        {proposal.url_final && <External url={proposal.url_final}>Página analisada</External>}
        {proposal.evidencias.length > 0 ? <ul>{proposal.evidencias.map((e,i) => <li key={i}><strong>{fields[e.campo] || e.campo}: {e.evidencia}</strong><br />{e.metodo} · <External url={e.origem}>Origem da evidência</External></li>)}</ul> : <p>Nenhuma correspondência comprovada pela leitura. Isso não confirma que o site seja de outra empresa.</p>}
        {proposal.erro && <p>Falha de verificação: {proposal.erro.tipo}. Nenhuma confirmação aplicada.</p>}
      </div>}
      {association.estado !== 'confirmado' && <form className="ed-form" onSubmit={e => { e.preventDefault(); confirm.mutate() }}>
        <Field label="Evidência revisada do vínculo" hint="Descreva nome, endereço/filial, contato ou perfil social que você conferiu. Homônimos ou evidências insuficientes devem continuar pendentes."><textarea maxLength={2000} minLength={15} required value={note} onChange={e => { setNote(e.target.value); setReviewed(false) }} rows={3} /></Field>
        <label className="ed-check"><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} /> Conferi a associação desta URL à empresa e à filial.</label>
        <button className="ed-button" disabled={!reviewed || note.trim().length < 15 || confirm.isPending}>Confirmar associação do site</button>
      </form>}
    </>}
    {verify.isError && <Erro error={verify.error} />}{confirm.isError && <Erro error={confirm.error} />}{query.isError && <Erro error={query.error} />}
    {confirm.isSuccess && <p className="ed-success" role="status">Associação registrada; outros campos preservados.</p>}
    {(empresa.fonte_busca_url || empresa.fonte_mapa_url || empresa.links_fontes.length > 0) && <div className="ed-site-sources"><h3>Links de fontes · não são sites oficiais</h3>
      {empresa.fonte_busca_url && <p>Busca/referência: <External url={empresa.fonte_busca_url}>{empresa.fonte_busca_url}</External></p>}
      {empresa.fonte_mapa_url && <p>Mapa/localização: <External url={empresa.fonte_mapa_url}>{empresa.fonte_mapa_url}</External></p>}
      {empresa.links_fontes.filter(x => ![empresa.fonte_busca_url,empresa.fonte_mapa_url].includes(x.url)).map(x => <p key={x.url}>{x.tipo}: <External url={x.url}>{x.url}</External></p>)}
    </div>}
    {empresa.historico_site.length > 0 && <details><summary>Histórico da URL e da associação ({empresa.historico_site.length})</summary><ul>{empresa.historico_site.map((h,i) => <li key={i}>{date(h.registrado_em)} · {h.motivo}<br />Anterior: <External url={h.valor_anterior}>{h.valor_anterior}</External><br />Novo: {h.valor_novo || 'Nenhum site substituto'}{h.fonte_anterior.url && <><br /><External url={h.fonte_anterior.url}>Fonte anterior</External> · {h.fonte_anterior.verificacao}</>}</li>)}</ul></details>}
    <div className="ed-form-actions"><button className="ed-button" onClick={onEdit}>Revisar site / adicionar informações</button><button className="ed-button" onClick={onMaterials}>Enviar materiais manualmente</button><Link className="ed-button" to="/integracoes">Ver outras fontes disponíveis</Link></div>
    {empresa.associacao_site.estado!=='confirmado'&&<small>Sem site confirmado, continue pelo cadastro/upload manual ou pelas fontes configuradas. OpenStreetMap continua disponível para descoberta; Firecrawl exige chave e um site adequado, e não descobre um endereço substituto.</small>}
  </section>
}

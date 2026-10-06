import { Link } from 'react-router-dom'
import { useQuery,useMutation,useQueryClient } from '@tanstack/react-query'
import { libraryApi } from './libraryApi'
import { Erro,Loading,Field } from './shared'
export function ContextPanel({id}:{id:string}){
 const client=useQueryClient(),q=useQuery({queryKey:['ed','contexto',id],queryFn:()=>libraryApi.context(id)})
 const save=useMutation({mutationFn:libraryApi.choose.bind(null,id),onSuccess:d=>client.setQueryData(['ed','contexto',id],d)})
 if(q.isPending)return <Loading/>
 if(q.isError)return <Erro error={q.error}/>
 const d=q.data,chosen=d.items.map(x=>x.id)
 return <section className="ed-panel ed-form"><div className="ed-panel-head"><div><h2>O que será usado</h2><p>Seleção salva para a próxima exportação. Um pacote anterior mantém seu snapshot.</p></div><Link className="ed-button" to={`/biblioteca/contexto?lead=${id}`}>Contexto deste projeto</Link></div>
 <Field label="Perfil visual de referência"><select disabled={save.isPending} value={d.selecao.perfil} onChange={e=>save.mutate({...d.selecao,perfil:e.target.value})}><option value="">Identidade personalizada</option><option value="artistico">Editorial artístico · Débora</option><option value="comercio">Comércio editorial · BV</option><option value="celebracao">Serviço e celebração · AG</option></select></Field>
 <div className="ed-actions">{['composicao','tipografia','movimento','fotografia','copy','componentes'].map(k=><label className="ed-check" key={k}><input type="checkbox" disabled={save.isPending} checked={d.selecao.elementos.includes(k)} onChange={e=>save.mutate({...d.selecao,elementos:e.target.checked?[...d.selecao.elementos,k]:d.selecao.elementos.filter(x=>x!==k)})}/>{k}</label>)}</div>
 <details><summary>{d.items.length} itens · versões e origens</summary>{d.disponiveis.map(x=><label className="ed-context-option" key={x.id}><input type="checkbox" disabled={save.isPending} checked={chosen.includes(x.id)} onChange={e=>save.mutate({...d.selecao,selecionados:e.target.checked?[...chosen,x.id]:chosen.filter(k=>k!==x.id)})}/><span><strong>{x.titulo}</strong> · v{x.versao}<small>{x.tipo} / {x.escopo} · {x.origem}</small></span></label>)}</details>
 {d.conflitos.map((x,i)=><p key={i}>{x.titulo}: {x.motivo}</p>)}{d.pendencias.map(x=><p key={x} className="ed-alert">{x}</p>)}{save.isError&&<Erro error={save.error}/>}<small>Limite: {d.limite} caracteres. Referências não confirmam fatos. Skills chegam como instruções Markdown; nenhum script importado é executado.</small></section>
}

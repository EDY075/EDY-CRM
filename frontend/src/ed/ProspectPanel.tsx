import {useState} from 'react'
import {useQuery,useMutation,useQueryClient} from '@tanstack/react-query'
import {httpClient} from '@/services/httpClient'
import {Field,Erro,Loading} from './shared'

const labels={inicial:'Mensagem inicial',whatsapp:'Texto para WhatsApp',email_assunto:'Assunto do e-mail',email:'Texto do e-mail',resumo:'Resumo da proposta',acompanhamento:'Acompanhamento'}
type Draft=Record<keyof typeof labels,string>
function Editor({company,value}:{company:string;value:Draft|null}){
 const client=useQueryClient(),[draft,setDraft]=useState<Draft>({...Object.fromEntries(Object.keys(labels).map(k=>[k,''])),...value} as Draft)
 const save=useMutation({mutationFn:()=>httpClient.put('/api/ed/empresas/'+company+'/prospeccao',Object.fromEntries(Object.keys(labels).map(k=>[k,draft[k as keyof Draft]]))),onSuccess:()=>client.invalidateQueries({queryKey:['ed']})})
 return <section className="ed-panel ed-form"><h2>Prospecção para revisão</h2><p>Rascunhos editáveis. Salve antes de exportar: os seis textos entram em prospeccao.md. Nenhuma mensagem é enviada pelo CRM. Links locais só abrem neste computador; publicação e compartilhamento são etapas posteriores.</p><form onSubmit={e=>{e.preventDefault();save.mutate()}}><div className="ed-form-grid">{Object.entries(labels).map(([key,label])=><Field key={key} label={label}><textarea rows={key==='email'?5:3} maxLength={4000} value={draft[key as keyof Draft]} onChange={e=>{save.reset();setDraft({...draft,[key]:e.target.value})}}/></Field>)}</div><button className="ed-button" disabled={save.isPending}>Salvar textos de prospecção</button>{save.isSuccess&&<p role="status">Textos revisados salvos. Novas pesquisas preservam esta edição.</p>}{save.isError&&<Erro error={save.error}/>}</form></section>
}
export function ProspectPanel({company}:{company:string}){
 const q=useQuery({queryKey:['ed','prospeccao',company],queryFn:()=>httpClient.get<Draft|null>('/api/ed/empresas/'+company+'/prospeccao')})
 return q.isPending?<Loading/>:q.isError?<Erro error={q.error}/>:<Editor company={company} value={q.data}/>
}

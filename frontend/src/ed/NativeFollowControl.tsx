import {useQuery,useMutation,useQueryClient} from '@tanstack/react-query'
import {httpClient} from '@/services/httpClient'
import {Erro} from './shared'
interface Follow {ativo:boolean;estado:string;mensagem:string;origem:string;conta_aplicativo:{rotulo:string};conta_runtime:{rotulo:string}}
export function NativeFollowControl(){
 const client=useQueryClient(),q=useQuery({queryKey:['ed','conta-ativa'],queryFn:()=>httpClient.get<Follow>('/api/ed/runtime/conta-ativa'),refetchInterval:30000}),set=useMutation({mutationFn:(ativo:boolean)=>httpClient.put('/api/ed/runtime/conta-ativa',{ativo}),onSuccess:()=>client.invalidateQueries({queryKey:['ed']})})
 return <div><label className="ed-check"><input type="checkbox" checked={q.data?.ativo||false} disabled={set.isPending||!q.data} onChange={e=>set.mutate(e.target.checked)}/> Seguir conta ativa do Codex</label><p role="status">{q.data?.mensagem}</p>{q.data?.estado==='erro'&&q.data.ativo&&<button className="ed-button" disabled={set.isPending} onClick={()=>set.mutate(true)}>Revalidar sessão seguida</button>}<small>Aplicativo/cache: {q.data?.conta_aplicativo.rotulo||'Indisponível'} · runtime: {q.data?.conta_runtime.rotulo||'Indisponível'}. Novas sessões são conferidas pelo app-server. Troca entre duas contas no aplicativo ainda requer validação com o usuário.</small>{set.isError&&<Erro error={set.error}/>}</div>
}

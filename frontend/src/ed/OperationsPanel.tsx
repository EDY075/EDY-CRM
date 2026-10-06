import {useQuery,useMutation} from '@tanstack/react-query'
import {httpClient} from '@/services/httpClient'
import {useAccess} from './accessContext'
import {Erro} from './shared'

export function OperationsPanel(){
 const q=useQuery({queryKey:['ed','diagnostico'],queryFn:()=>httpClient.get<{banco:string;versao:string;worker:{na_fila:number;executando:number;rotinas:boolean}}>('/api/ed/operacao/diagnostico')})
 const backup=useMutation({mutationFn:()=>httpClient.post<{download:string;arquivos:number}>('/api/ed/operacao/backup',{})})
 return <section className="ed-panel ed-form"><h2>Diagnóstico e recuperação</h2><p>Backend v{q.data?.versao||'…'} · SQLite: {q.data?.banco||'Verificando…'}. Worker: {q.data?.worker.executando||0} executando, {q.data?.worker.na_fila||0} na fila. Rotinas: {q.data?.worker.rotinas?'processo ativo':'não inicializadas'}.</p><p>Após reinício, use Assistente → Execuções → Retomar checkpoints. Requisições pagas com resultado ambíguo exigem revisão, sem repetição automática.</p>{useAccess()?.ator?.papel==='administrador'&&<button className="ed-button" disabled={backup.isPending} onClick={()=>backup.mutate()}>Criar backup deste workspace</button>}{backup.data&&<p role="status">Backup de {backup.data.arquivos} arquivos, sem credenciais/runtime. <a href={backup.data.download}>Baixar ZIP de recuperação</a></p>}<p>Restauração em pasta nova: consulte o manual e scripts/backup-edy.py. O banco atual nunca é sobrescrito pelo comando de restauração.</p>{q.isError&&<Erro error={q.error}/>} {backup.isError&&<Erro error={backup.error}/>}</section>
}

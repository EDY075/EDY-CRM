import {useNavigate} from 'react-router-dom'
import {useMutation} from '@tanstack/react-query'
import {httpClient} from '@/services/httpClient'
import {useAccess} from './accessContext'
import {Erro} from './shared'
export function RefinePreviewButton({company,build}:{company:string;build:string}){
 const navigate=useNavigate(),readonly=useAccess()?.ator?.papel==='leitura'
 const m=useMutation({mutationFn:()=>httpClient.post<{url:string}>(`/api/ed/empresas/${company}/construcoes/${build}/conversa`,{}),onSuccess:r=>navigate(r.url)})
 return <><button className="ed-button" disabled={readonly||m.isPending} onClick={()=>m.mutate()}>{m.isPending?'Abrindo conversa…':'Refinar site'}</button>{m.isError&&<Erro error={m.error}/>}</>
}

import {useEffect, useState} from 'react'
import {useQuery} from '@tanstack/react-query'
import {httpClient} from '@/services/httpClient'
interface RuntimeProof {conta_nativa_selecionada?:{identificador:string};acessos_modelos?:{modo:string;modelo:string;conta:string;estado:string;ultima_execucao_concluida?:string}[]}
export function useCreationMode(){
 const runtime=useQuery({queryKey:['ed','runtime'],queryFn:()=>httpClient.get<RuntimeProof>('/api/ed/runtime')})
 const account=runtime.data?.conta_nativa_selecionada?.identificador
 const validated=!!account&&runtime.data?.acessos_modelos?.some(x=>x.modo==='plano'&&x.modelo==='gpt-6.1-sol'&&x.conta===account&&(x.estado==='execucao_concluida'||x.estado==='acesso_nao_validado'&&!!x.ultima_execucao_concluida))
 const preferences=useQuery({queryKey:['ed','provedores'],queryFn:()=>httpClient.get<{config:{motor:string}}>('/api/ed/provedores')})
 const [generation,setValue]=useState('codex_nativo'),[chosen,setChosen]=useState(false)
 useEffect(()=>{if(preferences.data&&!chosen)setValue(preferences.data.config.motor)},[preferences.data,chosen])
 useEffect(()=>{if(validated&&!chosen&&!preferences.data)setValue('codex_nativo')},[validated,chosen,preferences.data])
 return {generation,validated,setGeneration:(value:string)=>{setChosen(true);setValue(value)}}
}

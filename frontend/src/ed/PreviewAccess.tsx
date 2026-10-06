import {useEffect,useRef,useState} from 'react'
import {Link,useParams} from 'react-router-dom'
import {useMutation,useQuery} from '@tanstack/react-query'
import {ArrowLeft,ArrowUpRight,Monitor,Smartphone} from 'lucide-react'
import {httpClient} from '@/services/httpClient'
import {useAccess} from './accessContext'
import {Badge,Erro,Loading,ResearchProgress} from './shared'

import {RefinePreviewButton} from './PreviewActions'
import {previewLabels,type PreviewProject} from './previewState'

export function PreviewPage(){
 const {company='',build=''}=useParams(),readonly=useAccess()?.ator?.papel==='leitura'
 const root=`/api/ed/empresas/${company}/construcoes/${build}`
 const q=useQuery({queryKey:['ed','preview',company,build],queryFn:()=>httpClient.get<PreviewProject>(root+'/disponibilidade'),retry:1})
 const lead=useQuery({queryKey:['ed','preview-name',company],queryFn:()=>httpClient.get<{nome:string}>(`/api/ed/empresas/${company}`)})
 const [url,setUrl]=useState(''),[phone,setPhone]=useState(()=>window.matchMedia('(max-width:800px)').matches),[loaded,setLoaded]=useState(false)
 const initialized=useRef(false),frame=useRef<HTMLDivElement>(null)
 const [frameSize,setFrameSize]=useState({width:390,height:620})
 useEffect(()=>{const el=frame.current;if(!el)return;const observer=new ResizeObserver(entries=>{const b=entries[0].contentRect;setFrameSize({width:b.width,height:b.height})});observer.observe(el);return()=>observer.disconnect()},[url,phone])
 const open=useMutation({mutationFn:()=>httpClient.post<{url:string}>(root+'/abrir',{}),onSuccess:r=>{setUrl(r.url);setLoaded(false);void q.refetch()}})
 useEffect(()=>{if(q.data&&!initialized.current){initialized.current=true;if(!readonly)open.mutate();else if(q.data.url_ativa)setUrl(q.data.url_ativa)}},[q.data,readonly,open])
 const renderWidth=phone?390:Math.max(1080,frameSize.width),scale=Math.min(1,frameSize.width/renderWidth)
 if(q.isPending)return <Loading/>
 if(q.isError)return <><Link className="ed-back" to="/previas">Voltar às prévias</Link><Erro error={q.error}/></>
 return <section className="ed-preview-viewer">
  <header className="ed-page-head"><div><Link className="ed-back" to="/previas"><ArrowLeft size={16}/> Voltar às prévias</Link><h1>{lead.data?.nome||'Prévia do projeto'}</h1><p>Versão salva · {q.data.modelo||'Construção local'} · aprovação visual e comercial pendentes</p></div><Badge tone={url&&loaded?'green':'amber'}>{open.isPending?'Iniciando servidor…':url&&loaded?'HTML carregado':previewLabels[q.data.estado]}</Badge></header>
  <div className="ed-actions ed-preview-toolbar"><button className="ed-button" aria-pressed={!phone} onClick={()=>setPhone(false)}><Monitor size={16}/> Desktop</button><button className="ed-button" aria-pressed={phone} onClick={()=>setPhone(true)}><Smartphone size={16}/> Celular</button>{url&&<a className="ed-button" href={url} target="_blank" rel="noopener noreferrer">Abrir em nova aba <ArrowUpRight size={16}/></a>}<RefinePreviewButton company={company} build={build}/><Link className="ed-button" to={'/empresas/'+company}>Ficha da empresa</Link></div>
  {open.isPending&&<ResearchProgress active label="Abrindo prévia" message="Verificando HTML, recursos e servidor da versão selecionada…"/>}
  {open.isError&&<div className="ed-panel ed-form"><Erro error={open.error}/><p>A versão salva não será substituída. Confira arquivos e versões na ficha; isso não exige chave de fornecedor.</p><button className="ed-button" onClick={()=>open.mutate()}>Tentar recuperar servidor</button><Link className="ed-button" to={`/empresas/${company}?aba=construir`}>Recuperar arquivos ou refinar construção</Link></div>}
  {readonly&&!url&&<p role="status">Um editor precisa iniciar o servidor local. Seu acesso de leitura não executa processos.</p>}
  {url&&<div ref={frame} className={'ed-preview-browser '+(phone?'phone':'desktop')}><iframe title={'Prévia HTML de '+(lead.data?.nome||'empresa')} src={url} style={{width:renderWidth,height:frameSize.height/scale,transform:`scale(${scale})`,transformOrigin:'top left'}} onLoad={()=>setLoaded(true)} sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox" referrerPolicy="no-referrer" allow="camera 'none'; microphone 'none'; geolocation 'none'"/></div>}
  <details className="ed-panel ed-form"><summary>Versão e verificação técnica</summary><p>Construção {build}. {q.data.motivo}</p><p>O carregamento do HTML não representa aprovação estética nem confirma dados comerciais.</p></details>
 </section>
}

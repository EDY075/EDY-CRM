import {useState,useRef,useEffect} from 'react'
import {Mic,Square,VolumeX} from 'lucide-react'
import {csrfHeaders} from './accessState'
import {Erro} from './shared'

export function VoiceControl({onText,disabled=false}:{onText:(text:string)=>void;disabled?:boolean}){
 const [state,setState]=useState('pronto'),[blob,setBlob]=useState<Blob|null>(null),[url,setUrl]=useState(''),[error,setError]=useState<Error|null>(null),[seconds,setSeconds]=useState(0)
 const recorder=useRef<MediaRecorder|null>(null),stream=useRef<MediaStream|null>(null),timer=useRef<ReturnType<typeof setInterval>|null>(null),discard=useRef(false),mounted=useRef(true),controller=useRef<AbortController|null>(null),key=useRef('')
 function close(){if(timer.current)clearInterval(timer.current);timer.current=null;stream.current?.getTracks().forEach(x=>x.stop());stream.current=null}
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;discard.current=true;if(recorder.current?.state==='recording')recorder.current.stop();close();controller.current?.abort()}},[])
 useEffect(()=>{if(!blob){setUrl('');return}const v=URL.createObjectURL(blob);setUrl(v);return()=>URL.revokeObjectURL(v)},[blob])
 async function record(){
  setError(null);setBlob(null)
  if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==='undefined'){setError(new Error('Captura indisponível neste navegador. Use chat por texto; transcrição não depende do reconhecimento do navegador.'));return}
  setState('permissao');discard.current=false
  try{
   const s=await navigator.mediaDevices.getUserMedia({audio:true});if(!mounted.current||discard.current){s.getTracks().forEach(t=>t.stop());return}stream.current=s
   const mime=['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus'].find(x=>MediaRecorder.isTypeSupported(x)),r=new MediaRecorder(s,mime?{mimeType:mime}:undefined),parts:BlobPart[]=[];recorder.current=r;key.current=crypto.randomUUID()
   r.ondataavailable=e=>{if(e.data.size)parts.push(e.data)}
   r.onstop=()=>{close();if(!mounted.current)return;if(!discard.current){setBlob(new Blob(parts,{type:r.mimeType}));setState('capturado')}else setState('pronto')}
   r.onerror=()=>{discard.current=true;close();if(mounted.current){setState('erro');setError(new Error('A gravação falhou. Confira o microfone e tente novamente.'))}}
   r.start();setSeconds(0);setState('gravando');let elapsed=0
   timer.current=setInterval(()=>{elapsed++;setSeconds(elapsed);if(elapsed>=60&&r.state==='recording')r.stop()},1000)
  }catch(e){close();setState('erro');setError(new Error(e instanceof Error?e.message:'Permissão do microfone não concedida.'))}
 }
 async function transcribe(){if(!blob)return;setState('processando');setError(null);controller.current=new AbortController()
  try{const f=new FormData();f.append('arquivo',blob,'comando');f.append('chave',key.current);const response=await fetch('/api/ed/voz/transcrever',{method:'POST',headers:csrfHeaders(),body:f,signal:controller.current.signal});const d=await response.json();if(!response.ok)throw new Error(d.erro);onText(d.texto);setState('transcrito')}
  catch(e){if(e instanceof Error&&e.name==='AbortError'){setState('capturado');return}setState('capturado');setError(e instanceof Error?e:new Error('Transcrição indisponível; gravação local preservada.'))}
 }
 function cancel(){discard.current=true;if(recorder.current?.state==='recording')recorder.current.stop();close();controller.current?.abort();setBlob(null);setState('pronto')}
 return <details className="ed-voice"><summary><Mic size={16}/> Comando por voz</summary><p>Ao iniciar, o navegador pede permissão. Captura local de até 60 segundos. Envio à API somente ao clicar Transcrever; revise o texto antes de executá-lo.</p><div className="ed-actions"><button type="button" className="ed-button" disabled={disabled||['gravando','processando','permissao'].includes(state)} onClick={record}><Mic size={16}/> Iniciar gravação</button>{state==='gravando'&&<button type="button" className="ed-button" onClick={()=>recorder.current?.stop()}><Square size={16}/> Parar · {seconds}s</button>}{['gravando','processando','permissao'].includes(state)&&<button type="button" className="ed-button" onClick={cancel}>Cancelar</button>}</div><p role="status">{state==='processando'?'Transcrição solicitada ao fornecedor…':state==='gravando'?'Gravando; não enviado ao servidor.':state==='transcrito'?'Texto inserido no campo do chat; revise antes de executar.':state==='capturado'?'Gravação disponível. Transcrição requer credencial própria de voz.':''}</p>{blob&&<><audio controls src={url}/><div className="ed-actions"><button type="button" className="ed-button" disabled={disabled||state==='processando'} onClick={transcribe}>Transcrever em português</button><a className="ed-button" href={url} download={'comando-edy.'+(blob.type.includes('mp4')?'mp4':blob.type.includes('ogg')?'ogg':'webm')}>Salvar áudio local</a><button className="ed-button" type="button" onClick={cancel}>Descartar captura</button></div></>}{error&&<Erro error={error}/>}</details>
}

export function SpokenReply({text}:{text:string}){
 const [muted,setMuted]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState<Error|null>(null),audio=useRef<HTMLAudioElement|null>(null),url=useRef(''),controller=useRef<AbortController|null>(null)
 function stop(){controller.current?.abort();audio.current?.pause();if(url.current)URL.revokeObjectURL(url.current);url.current='';audio.current=null;setBusy(false)}
 useEffect(()=>()=>{controller.current?.abort();audio.current?.pause();if(url.current)URL.revokeObjectURL(url.current)},[])
 async function speak(){if(muted)return;setBusy(true);setError(null);controller.current=new AbortController();try{const r=await fetch('/api/ed/voz/falar',{method:'POST',headers:{'Content-Type':'application/json',...csrfHeaders()},body:JSON.stringify({texto:text.slice(0,2000)}),signal:controller.current.signal});if(!r.ok)throw new Error((await r.json()).erro);if(url.current)URL.revokeObjectURL(url.current);url.current=URL.createObjectURL(await r.blob());audio.current=new Audio(url.current);audio.current.onended=stop;await audio.current.play()}catch(e){if(e instanceof Error&&e.name!=='AbortError')setError(e);setBusy(false)}}
 return <div className="ed-spoken"><label className="ed-check"><input type="checkbox" checked={muted} onChange={e=>{setMuted(e.target.checked);if(e.target.checked)stop()}}/><VolumeX size={14}/> Silenciar resposta</label><small>Voz gerada por IA · requer API de voz configurada.</small><button className="ed-button" disabled={muted||busy} onClick={speak}>Ouvir resposta</button>{busy&&<button className="ed-button" onClick={stop}>Interromper áudio</button>}{error&&<Erro error={error}/>}</div>
}

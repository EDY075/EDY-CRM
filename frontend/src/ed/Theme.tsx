import type { ThemeState } from './useTheme'
import {useEffect,useRef,useState} from 'react'
import { Moon, Pause, Play, Sun, Sparkles, Check } from 'lucide-react'
import './themes.css'
import './nebula-mirror.css'
import './glass.css'
import './universe-glass.css'
import './material-themes.css'
import {UniverseImage} from './UniverseImage'

const choices = [
  { id: 'claro', label: 'Claro', icon: Sun }, { id: 'escuro', label: 'Escuro', icon: Moon },
  { id: 'nebulosa', label: 'Nebulosa', icon: Sparkles },
] as const

export function Nebula({ stopped,quality='auto',pointer=false,theme='nebulosa' }: { stopped: boolean;quality?:'auto'|'economica'|'alta';pointer?:boolean;theme:ThemeState['theme'] }) {
  const [slow,setSlow]=useState(false)
  const economy=quality==='economica'||quality==='auto'&&(slow||navigator.hardwareConcurrency<=4||matchMedia('(max-width: 768px)').matches)
  useEffect(()=>{
    if(stopped||quality!=='auto')return
    let frame=0,start=0,count=0,stalls=0,last=0
    function sample(now:number){if(!start)start=now;if(last&&now-last>35)stalls++;last=now;count++;if(count<90&&now-start<4000)frame=requestAnimationFrame(sample);else setSlow(stalls>count*.2)}
    frame=requestAnimationFrame(sample);return()=>cancelAnimationFrame(frame)
  },[stopped,quality])
  return <div className={`ed-nebula ed-nebula-glass${stopped ? ' is-paused' : ''}${economy?' is-economy':''}`} data-quality={economy?'economica':'alta'} aria-hidden="true">
    <UniverseImage stopped={stopped} economy={economy} theme={theme}/>
    <PointerTrail enabled={pointer&&!stopped&&!economy}/>
  </div>
}

function PointerTrail({enabled}:{enabled:boolean}){
 const ref=useRef<HTMLDivElement>(null)
 useEffect(()=>{
  if(!enabled||!matchMedia('(pointer:fine) and (hover:hover)').matches||matchMedia('(prefers-reduced-motion:reduce)').matches)return
  const nodes=Array.from(ref.current?.children||[]) as HTMLElement[];let last=0,index=0
  const cancel=()=>nodes.forEach(x=>x.getAnimations().forEach(a=>a.cancel()))
  const move=(event:PointerEvent)=>{
   if(event.pointerType!=='mouse'||document.hidden||event.target instanceof Element&&event.target.closest('input,textarea,select,[contenteditable],table')){cancel();return}
   const now=performance.now();if(now-last<45)return;last=now
   const node=nodes[index++%nodes.length];node.getAnimations().forEach(a=>a.cancel())
   node.style.transform=`translate3d(${event.clientX}px,${event.clientY}px,0)`
   node.animate([{opacity:.34,transform:`translate3d(${event.clientX}px,${event.clientY}px,0) scale(1)`},{opacity:0,transform:`translate3d(${event.clientX-5}px,${event.clientY+6}px,0) scale(.4)`}],{duration:240,easing:'cubic-bezier(.2,.7,.3,1)'})
  }
  window.addEventListener('pointermove',move,{passive:true});window.addEventListener('blur',cancel)
  return()=>{window.removeEventListener('pointermove',move);window.removeEventListener('blur',cancel);cancel()}
 },[enabled])
 return <div ref={ref} className="ed-pointer-trail">{Array.from({length:5},(_,i)=><span key={i}/>)}</div>
}

export function ThemeChoices({state}:{state:ThemeState}) {
 const presets=[{label:'Equilibrado',value:.26},{label:'Mais transparente',value:.18},{label:'Mais legível',value:.58}]
 return <div className="ed-theme-settings"><div className="ed-theme-options">{choices.map(x=><button key={x.id} className="ed-appearance-choice" aria-pressed={state.theme===x.id} onClick={()=>state.setTheme(x.id)}><span className={`ed-theme-preview ${x.id}`} aria-hidden="true"/><x.icon size={16}/>{x.label}{state.theme===x.id&&<Check size={16}/>}</button>)}</div>
 <>
 <div className="ed-glass-preview"><strong>{state.theme==='claro'?'Água cristalina, vidro e luz.':state.theme==='escuro'?'Fumaça suave, vidro e profundidade.':'Uma superfície, um universo.'}</strong><p>Texto nítido. Fundo visível através do vidro.</p><span className="ed-badge">Prévia do material atual</span></div>
 <div className="ed-glass-presets" role="group" aria-label="Material dos painéis">{presets.map(p=><button key={p.label} className="ed-button" aria-pressed={Math.abs(state.surfaceOpacity-p.value)<.01} onClick={()=>state.setSurfaceOpacity(p.value)}>{p.label}</button>)}</div>
 {state.reduced?<p className="ed-motion-note">Movimento reduzido · {state.theme==='nebulosa'?'universo':'fundo'} estático</p>:<button className="ed-button" aria-pressed={state.paused} onClick={()=>state.setPaused(!state.paused)}>{state.paused?<Play size={16}/>:<Pause size={16}/>} {state.paused?'Retomar movimento':'Pausar movimento'}</button>}
 <details className="ed-appearance-advanced"><summary>Ajustar transparência, fundo e efeitos</summary><div className="ed-form-grid">
 <label className="ed-field"><span>Transparência das superfícies</span><input type="range" min="28" max="82" step="1" value={Math.round((1-state.surfaceOpacity)*100)} onChange={e=>state.setSurfaceOpacity(1-Number(e.target.value)/100)}/><small>{Math.round((1-state.surfaceOpacity)*100)}% · texto e controles permanecem opacos</small></label>
 <label className="ed-field"><span>{state.theme==='nebulosa'?'Intensidade do universo':'Intensidade do fundo'}</span><input type="range" min="0.2" max="1" step="0.1" value={state.intensity} onChange={e=>state.setIntensity(Number(e.target.value))}/><small>{Math.round(state.intensity*100)}% · intensidade das cores, sem escurecer a arte</small></label>
 <label className="ed-field"><span>Qualidade do fundo</span><select value={state.quality} onChange={e=>state.setQuality(e.target.value as ThemeState['quality'])}><option value="auto">Adaptativa</option><option value="economica">Econômica</option><option value="alta">Textura completa</option></select></label>
 <label className="ed-check"><input type="checkbox" checked={state.pointer} onChange={e=>state.setPointer(e.target.checked)}/> Rastro discreto do ponteiro</label></div><small>Movimento suspenso em aba oculta. Rastro somente com mouse, fora de campos e tabelas; desativado em modo econômico e movimento reduzido.</small></details></>
 <p className="ed-muted">A seleção fica salva neste navegador e é aplicada imediatamente.</p></div>
}

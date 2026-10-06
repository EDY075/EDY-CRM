import {useEffect,useRef} from 'react'
import universe from './assets/edy-universe.webp'
import water from './assets/edy-water.webp'
import smoke from './assets/edy-smoke.webp'

/** Uma imagem composta; movimento no compositor, sem redesenhar canvas por frame. */
export function UniverseImage({stopped,economy,theme}:{stopped:boolean;economy:boolean;theme:'claro'|'escuro'|'nebulosa'}){
 const ref=useRef<HTMLImageElement>(null)
 useEffect(()=>{
  const image=ref.current
  if(!image||stopped)return
  let animation:Animation|undefined,disposed=false
  const move=()=>{
   if(disposed)return
   const from=getComputedStyle(image).transform
   const target=`translate3d(${(Math.random()*2-1)*4.5}%,${(Math.random()*2-1)*4.5}%,0) scale(${1.12+Math.random()*.08})`
   animation=image.animate([{transform:from},{transform:target}],{duration:(economy?14000:9000)+Math.random()*5000,easing:'cubic-bezier(.45,0,.55,1)',fill:'forwards'})
   animation.onfinish=()=>{image.style.transform=target;animation?.cancel();move()}
  }
  move()
  return()=>{disposed=true;image.style.transform=getComputedStyle(image).transform;animation?.cancel()}
 },[stopped,economy])
 return <><img ref={ref} className="ed-cloud ed-universe-image" src={theme==='claro'?water:theme==='escuro'?smoke:universe} alt="" decoding="async" fetchPriority="high"/><span className="ed-universe-brand">EDY</span></>
}

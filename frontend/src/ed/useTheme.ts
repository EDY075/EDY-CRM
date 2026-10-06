import { useEffect, useLayoutEffect, useState } from 'react'

type Theme = 'claro' | 'escuro' | 'nebulosa'
const isTheme = (value: string | null): value is Theme => ['claro', 'escuro', 'nebulosa'].includes(value || '')
function saved(key: string) { try { return localStorage.getItem(key) } catch { return null } }
function remember(key: string, value: string) { try { localStorage.setItem(key, value) } catch { /* Navegação privada sem armazenamento. */ } }

export function useTheme(preferenceScope = 'local') {
  const [theme, setTheme] = useState<Theme>(() => {
    const value = saved('ed-crm.theme'); return isTheme(value) ? value : 'claro'
  })
  const [paused, setPaused] = useState(() => saved('ed-crm.motion-paused') === 'true')
  const [intensity,setIntensity]=useState(()=>{const v=Number(saved('ed-crm.nebula-intensity'));return v>=.2&&v<=1?v:.7})
  const [quality,setQuality]=useState<'auto'|'economica'|'alta'>(()=>{const q=saved('ed-crm.nebula-quality');return q==='economica'||q==='alta'?q:'auto'})
  const [pointer,setPointer]=useState(()=>saved('ed-crm.nebula-pointer')==='true')
  const glassKey = 'ed-crm.glass-opacity.' + preferenceScope
  const readGlass = () => { const value = Number(saved(glassKey)); return value >= .18 && value <= .72 ? value : .26 }
  const [glass, setGlass] = useState(() => ({ key: glassKey, value: readGlass() }))
  const surfaceOpacity = glass.key === glassKey ? glass.value : readGlass()
  const setSurfaceOpacity = (value: number) => setGlass({ key: glassKey, value })
  useLayoutEffect(() => {
    document.documentElement.style.setProperty('--ed-glass-opacity', String(surfaceOpacity))
    remember(glassKey, String(surfaceOpacity))
  }, [surfaceOpacity, glassKey])
  useEffect(()=>remember('ed-crm.nebula-quality',quality),[quality])
  useEffect(()=>remember('ed-crm.nebula-pointer',String(pointer)),[pointer])
  useLayoutEffect(()=>{document.documentElement.style.setProperty('--ed-nebula-intensity',String(intensity));remember('ed-crm.nebula-intensity',String(intensity))},[intensity])
  const [hidden, setHidden] = useState(document.hidden)
  const [reduced, setReduced] = useState(() => matchMedia('(prefers-reduced-motion: reduce)').matches)
  useLayoutEffect(() => { document.documentElement.dataset.theme = theme; remember('ed-crm.theme', theme) }, [theme])
  useEffect(() => { remember('ed-crm.motion-paused', String(paused)) }, [paused])
  useEffect(() => {
    const media = matchMedia('(prefers-reduced-motion: reduce)')
    const motion = () => setReduced(media.matches), visibility = () => setHidden(document.hidden)
    media.addEventListener('change', motion); document.addEventListener('visibilitychange', visibility)
    const storage = (event: StorageEvent) => {
      if (event.key === 'ed-crm.theme' && isTheme(event.newValue)) setTheme(event.newValue)
      if (event.key === 'ed-crm.motion-paused') setPaused(event.newValue === 'true')
      if(event.key==='ed-crm.nebula-intensity'){const v=Number(event.newValue);if(v>=.2&&v<=1)setIntensity(v)}
      if(event.key==='ed-crm.nebula-quality'&&['auto','economica','alta'].includes(event.newValue||''))setQuality(event.newValue as 'auto'|'economica'|'alta')
      if(event.key==='ed-crm.nebula-pointer')setPointer(event.newValue==='true')
      if(event.key===glassKey){const v=Number(event.newValue);if(v>=.18&&v<=.72)setGlass({key:glassKey,value:v})}
    }
    window.addEventListener('storage', storage)
    return () => { media.removeEventListener('change', motion); document.removeEventListener('visibilitychange', visibility); window.removeEventListener('storage', storage) }
  }, [glassKey])
  return { theme, setTheme, paused, setPaused, intensity,setIntensity,quality,setQuality,pointer,setPointer,surfaceOpacity,setSurfaceOpacity,reduced, stopped: paused || hidden || reduced }
}
export type ThemeState = ReturnType<typeof useTheme>

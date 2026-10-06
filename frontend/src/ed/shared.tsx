import { cloneElement, useId,useRef,useState } from 'react'
import type { ReactElement, ReactNode,ComponentProps } from 'react'
import { AlertCircle, ArrowUpRight, LoaderCircle } from 'lucide-react'

export function Badge({ children, tone = '' }: { children: ReactNode; tone?: string }) {
  return <span className={`ed-badge ${tone}`}>{children}</span>
}
export function Erro({ error }: { error: unknown }) {
  return <div className="ed-alert error" role="alert"><AlertCircle size={18} /><span>{error instanceof Error ? error.message : String(error)}</span></div>
}
export function Loading() {
  return <div className="ed-loading" role="status"><LoaderCircle size={20} className="ed-spin" /> Carregando informações…</div>
}
export function Empty({ title, children }: { title: string; children: ReactNode }) {
  return <div className="ed-empty"><span className="ed-empty-symbol" aria-hidden="true">↗</span><h2>{title}</h2><p>{children}</p></div>
}
export function Field({ label, children, hint }: { label: string; children: ReactElement<{ id?: string; 'aria-describedby'?: string }>; hint?: string }) {
  const id = useId()
  return <div className="ed-field"><label htmlFor={id}>{label}</label>{cloneElement(children, { id, 'aria-describedby': hint ? `${id}-hint` : undefined })}{hint && <small id={`${id}-hint`}>{hint}</small>}</div>
}
export function External({ url, children }: { url: string; children: ReactNode }) {
  if (!/^https?:\/\//i.test(url)) return <span>{children} · link inválido para revisão</span>
  return <a className="ed-link" href={url} target="_blank" rel="noopener noreferrer">{children}<ArrowUpRight size={14} /></a>
}

export function FileInput(props:Omit<ComponentProps<'input'>,'type'>){
 const ref=useRef<HTMLInputElement>(null),[name,setName]=useState('')
 return <div className="ed-file-input"><input {...props} ref={ref} type="file" tabIndex={-1} aria-hidden="true" className="ed-sr-only" onChange={e=>{setName(e.target.files?.[0]?.name||'');props.onChange?.(e)}}/><button type="button" className="ed-button" aria-describedby={props['aria-describedby']} disabled={props.disabled} onClick={()=>ref.current?.click()}>Escolher arquivo</button><small aria-live="polite">{name||'Nenhum arquivo selecionado'}</small></div>
}

export function ResearchProgress({active=false,value,message,label='Progresso da pesquisa',failed=false}:{active?:boolean;value?:number;message:string;label?:string;failed?:boolean}){
 return <div className={'ed-research-meter'+(failed?' failed':'')} aria-busy={active}><p role="status" aria-live="polite">{active&&<LoaderCircle size={16} className="ed-spin"/>}{message}</p><progress max={100} value={typeof value==='number'?Math.min(100,Math.max(0,value)):active?undefined:0} aria-label={label}/>{active&&<small>Em andamento · o progresso indica etapas, não uma previsão de tempo.</small>}{failed&&<small>Pesquisa interrompida. A barra não indica conclusão; resultados parciais foram preservados.</small>}</div>
}

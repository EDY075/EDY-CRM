import {AccessGate} from './Access'
import { useEffect,useRef,Suspense,lazy } from 'react'
import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { Building2, Settings, BookOpen, MapPin, Menu, Sparkles, PanelsTopLeft } from 'lucide-react'
import { queryClient } from '@/lib/queryClient'
import { EmpresasPage } from './EmpresasPage'
import { BuscaPage, CampanhasPage } from './PesquisaPages'
import { FichaPage } from './FichaPage'
import { EmpresaForm } from './EmpresaForm'
import { Nebula } from './Theme'
import { SettingsPage } from './SettingsPage'
import { LibraryPage } from './LibraryPage'
import {useAccess} from './accessContext'
import {PreviewsPage} from './PreviewsPage'
const OperationalPage=lazy(()=>import('./OperationalPage').then(m=>({default:m.OperationalPage})))
const AssistantPage=lazy(()=>import('./AssistantPage').then(m=>({default:m.AssistantPage})))
const SiteRefinementPage=lazy(()=>import('./SiteRefinementPage').then(m=>({default:m.SiteRefinementPage})))
const PreviewPage=lazy(()=>import('./PreviewAccess').then(m=>({default:m.PreviewPage})))
import './siteRefinement.css'
import { useTheme } from './useTheme'
function NavigationLinks(){return <><NavLink to="/" end><Sparkles size={18}/> Início</NavLink><NavLink to="/leads"><Building2 size={18}/> Leads</NavLink><NavLink to="/previas"><PanelsTopLeft size={18}/> Prévias</NavLink><NavLink to="/biblioteca/contexto"><BookOpen size={18}/> Biblioteca</NavLink></>}

function Shell() {
  const location = useLocation()
  const mobileMenu=useRef<HTMLDetailsElement>(null)
  const access=useAccess(),workspaceName=access?.workspaces.find(w=>w.id===access.ator?.workspace)?.nome||'Meu workspace'
  const theme = useTheme(`${access?.ator?.workspace||'local'}:${access?.ator?.id||'local'}`)
  const segment=location.pathname.startsWith('/configuracoes')?'Configurações':location.pathname.startsWith('/biblioteca')?'Biblioteca':location.pathname.startsWith('/previas')?'Prévias':location.pathname==='/'||location.pathname.startsWith('/assistente')?'Início':'Leads'
  useEffect(() => { if(mobileMenu.current)mobileMenu.current.open=false;window.scrollTo(0, 0); document.getElementById('ed-main')?.focus() }, [location.pathname])
  return <div className={'ed-app'+(location.pathname.includes('/refinar/')?' ed-refinement-workspace':'')}>
    <Nebula theme={theme.theme} stopped={theme.stopped} quality={theme.quality} pointer={theme.pointer} />
    <a className="ed-skip" href="#ed-main">Ir para o conteúdo</a>
    <aside className="ed-sidebar" aria-label="Workspace e navegação">
      <NavLink className="ed-brand" to="/"><svg className="ed-brand-symbol" viewBox="0 0 40 40" aria-hidden="true"><path d="M8 10h24v6H14v6h12v6H14v6H8z" fill="currentColor"/><path d="m24 22 8-8v20h-8z" fill="currentColor" opacity=".55"/></svg><div>EDY CRM<small>PROSPECÇÃO & CRIAÇÃO</small></div></NavLink>
      <div className="ed-workspace"><span className="ed-avatar">E</span><div>{workspaceName}<small>{access?.ator?.modo==='local'?'Uso pessoal · local':access?.ator?.nome+' · '+access?.ator?.papel}</small></div><span className="ed-dot" /></div>
      <p className="ed-nav-label">WORKSPACE</p>
      <nav aria-label="Navegação principal"><NavigationLinks/></nav>
      <details ref={mobileMenu} className="ed-mobile-menu"><summary><Menu size={16}/> Menu do workspace</summary><nav aria-label="Navegação mobile"><NavigationLinks/><NavLink to="/configuracoes/geral"><Settings size={16}/> Configurações</NavLink></nav></details>
      <div className="ed-side-guide"><p>Seu próximo projeto começa com uma empresa.</p><NavLink to="/nova-busca">Pesquisar empresas ↗</NavLink></div>
      <NavLink className="ed-settings-link" to="/configuracoes/geral"><Settings size={17}/> Configurações</NavLink><footer><MapPin size={14} /><span>© OpenStreetMap contributors<br /><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">Dados sob ODbL 1.0</a></span></footer>
    </aside>
    <div className="ed-workarea"><header className="ed-topbar"><span className="ed-breadcrumb">{workspaceName} <span>/</span> {segment}</span><div className="ed-topbar-actions"><NavLink className="ed-button" to="/crm/dashboard">Visão do trabalho</NavLink>{!theme.reduced&&<button className="ed-button" aria-pressed={theme.paused} onClick={()=>theme.setPaused(!theme.paused)}>{theme.theme==='nebulosa'?(theme.paused?'Retomar universo':'Pausar universo'):(theme.paused?'Retomar fundo':'Pausar fundo')}</button>}</div></header>
      <main id="ed-main" tabIndex={-1}>
        <Suspense fallback={<p role="status">Carregando área do workspace…</p>}><Routes>
          <Route path="/" element={<AssistantPage home />} />
          <Route path="/leads" element={<EmpresasPage />} />
          <Route path="/empresas" element={<Navigate replace to="/leads" />} />
          <Route path="/previas" element={<PreviewsPage />} />
          <Route path="/previas/:company/:build" element={<PreviewPage key={location.pathname}/>} />
          <Route path="/crm/:area?" element={<OperationalPage />} />
          <Route path="/assistente" element={<AssistantPage />} />
          <Route path="/empresas/nova" element={<><div className="ed-page-head"><div><span className="ed-eyebrow">CADASTRO MANUAL</span><h1>Nova empresa</h1><p>Registre o que você conhece. O que faltar vira pendência.</p></div></div><EmpresaForm /></>} />
          <Route path="/empresas/:id" element={<FichaPage />} />
          <Route path="/empresas/:id/refinar/:session" element={<SiteRefinementPage key={location.pathname}/>} />
          <Route path="/nova-busca" element={<BuscaPage />} />
          <Route path="/campanhas" element={<CampanhasPage />} />
          <Route path="/integracoes" element={<Navigate replace to="/configuracoes/conexoes" />} />
          <Route path="/configuracoes/:area?" element={<SettingsPage theme={theme}/>} />
          <Route path="/biblioteca/:area?" element={<LibraryPage/>} />
          <Route path="*" element={<><h1>Página não encontrada</h1><NavLink to="/">Voltar às empresas</NavLink></>} />
        </Routes></Suspense>
      </main>
    </div>
  </div>
}
export default function EdApp() {
  return <QueryClientProvider client={queryClient}><BrowserRouter><AccessGate><Shell /></AccessGate></BrowserRouter></QueryClientProvider>
}

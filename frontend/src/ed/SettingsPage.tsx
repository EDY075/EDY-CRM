import { NavLink, useParams } from 'react-router-dom'
import { IntegracoesPage } from './PesquisaPages'
import { ThemeChoices } from './Theme'
import type { ThemeState } from './useTheme'
import { VaultPanel } from './VaultPanel'
import './knowledge.css'
import {AccessPanel} from './Access'
import {OperationsPanel} from './OperationsPanel'
import {ProvidersPanel} from './ProvidersPanel'
import {lazy,Suspense} from 'react'
import {Loading} from './shared'
const VisualProvidersPanel=lazy(()=>import('./VisualProvidersPanel').then(m=>({default:m.VisualProvidersPanel})))

export function SettingsPage({theme}:{theme:ThemeState}) {
 const {area='geral'}=useParams()
 return <><div className="ed-page-head"><div><span className="ed-eyebrow">WORKSPACE</span><h1>Configurações<span>.</span></h1><p>Preferências locais, aparência e acesso aos fornecedores.</p></div></div>
 <nav className="ed-settings-tabs" aria-label="Configurações">{[['geral','Geral'],['aparencia','Aparência'],['conexoes','Conexões']].map(([id,name])=><NavLink key={id} to={`/configuracoes/${id}`}>{name}</NavLink>)}</nav>
 {area==='geral'&&<section className="ed-panel ed-form"><h2>Seu ambiente de criação</h2><p>Preferências do workspace e proteção dos seus dados locais.</p><dl className="ed-facts"><div><dt>Preferência de execução</dt><dd>GPT-6.1 Sol · Alto · Padrão. O acesso é validado por execução real.</dd></div><div><dt>Fluxo</dt><dd>Pesquisar → revisar → preparar materiais → compor → exportar ou construir → refinar.</dd></div><div><dt>Dados</dt><dd>Banco e históricos preservados. Novas exportações geram versões independentes.</dd></div></dl><NavLink className="ed-button" to="/biblioteca/contexto">Abrir biblioteca de criação</NavLink></section>}
 {area==='aparencia'&&<section className="ed-panel ed-form"><h2>Aparência</h2><p>O tema do workspace é independente da identidade das landing pages.</p><ThemeChoices state={theme}/></section>}
 {area==='conexoes'&&<><Suspense fallback={<Loading/>}><VisualProvidersPanel/></Suspense><ProvidersPanel/><IntegracoesPage embedded/><details className="ed-panel ed-form"><summary>Armazenamento seguro das credenciais</summary><VaultPanel/></details></>}
 {area==='geral'&&<AccessPanel/>}
 {area==='geral'&&<details className="ed-panel ed-form"><summary>Diagnóstico e manutenção</summary><OperationsPanel/></details>}
 {!['geral','aparencia','conexoes'].includes(area)&&<p>Configuração não encontrada.</p>}
 </>
}

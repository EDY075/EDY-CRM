import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './ed/ed.css'
import App from './ed/EdApp.tsx'
import { ErrorBoundary } from './components/shared/ErrorBoundary.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)

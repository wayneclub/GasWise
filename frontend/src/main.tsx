import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { serviceWorkerUrl } from './lib/serviceWorker'

if ('serviceWorker' in navigator) {
  const register = () => {
    void navigator.serviceWorker.register(serviceWorkerUrl(import.meta.url), { scope: '/', updateViaCache: 'none' }).catch(() => {})
  }
  if (document.readyState === 'complete') {
    register()
  } else {
    window.addEventListener('load', register)
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

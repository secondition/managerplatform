import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';

const CHUNK_RELOAD_KEY = 'manager-platform:chunk-reload-at';
const CHUNK_RELOAD_COOLDOWN_MS = 10_000;

window.addEventListener('vite:preloadError', (event) => {
  event.preventDefault();
  const now = Date.now();
  const previousReload = Number(window.sessionStorage.getItem(CHUNK_RELOAD_KEY));
  if (Number.isFinite(previousReload) && now - previousReload < CHUNK_RELOAD_COOLDOWN_MS) return;

  window.sessionStorage.setItem(CHUNK_RELOAD_KEY, String(now));
  const reloadUrl = new URL(window.location.href);
  reloadUrl.searchParams.set('_app_reload', String(now));
  window.location.replace(reloadUrl);
});

const loadedUrl = new URL(window.location.href);
if (loadedUrl.searchParams.has('_app_reload')) {
  loadedUrl.searchParams.delete('_app_reload');
  window.history.replaceState(window.history.state, '', loadedUrl);
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

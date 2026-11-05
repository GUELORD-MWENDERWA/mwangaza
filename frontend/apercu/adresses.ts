// Adresses de l'aperçu (`make apercu`) : ses propres serveurs, lancés à chaque fois sur des ports
// à lui (`playwright.config.ts`), jamais ceux de `make dev-local`. Un serveur resté d'une ancienne
// session servait du vieux code (404 sur les nouvelles adresses, attente sans fin).
export const API_PORT = 8010;
export const ITIG = "http://itig-demo.localhost:5183/app/";
export const PORTAL = "http://localhost:5184/";
export const CONSOLE = "http://admin.localhost:5185/";
export const SITE = `http://localhost:${API_PORT}/`;
export const ITIG_API = `http://itig-demo.localhost:${API_PORT}/`;

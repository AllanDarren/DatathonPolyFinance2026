// L'application parle toujours à la vraie API.
// - VITE_API_URL : adresse de l'API (déploiement : URL API Gateway; local par défaut : make dev sur le port 8000).
// - VITE_MOCK=1 : faux backend local, réservé aux tests automatiques (Vitest). Jamais activé par défaut.
export const IS_MOCK: boolean = import.meta.env.VITE_MOCK === '1';

const configured = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '');
export const API_URL: string = configured || 'http://127.0.0.1:8000';

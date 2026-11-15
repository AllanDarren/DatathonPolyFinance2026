export const API_URL: string = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? '';
// Mode simulé si VITE_MOCK=1, ou si aucune URL d'API n'est fournie.
export const IS_MOCK: boolean = import.meta.env.VITE_MOCK === '1' || API_URL === '';

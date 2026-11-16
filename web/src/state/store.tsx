// État en mémoire uniquement (aucun localStorage, aucun cookie).
// Navigation par hash (#/fil, #/tester…) : le bouton Retour fonctionne et chaque écran a un lien direct.
// Après un rechargement, l'état est vide : un écran qui exige un profil renvoie à l'accueil.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { Consideration, FeedResponse, Persona, Portfolio, Profile } from '../types/contracts';

export type Step =
  | 'welcome' | 'questionnaire' | 'profile' | 'portfolio'
  | 'feed' | 'overview' | 'consider' | 'calendar';

/** Onglets du tableau de bord (une action principale par onglet). */
export const DASHBOARD_TABS: Step[] = ['feed', 'overview', 'consider', 'calendar'];

const HASH: Record<Step, string> = {
  welcome: '#/',
  questionnaire: '#/questionnaire',
  profile: '#/profil',
  portfolio: '#/portefeuille',
  feed: '#/fil',
  overview: '#/apercu',
  consider: '#/tester',
  calendar: '#/calendrier',
};
const BY_HASH: Record<string, Step> = Object.fromEntries(Object.entries(HASH).map(([k, v]) => [v, k as Step]));

export function hrefFor(step: Step): string {
  return HASH[step];
}

export function stepFromHash(hash: string): Step {
  return BY_HASH[hash || '#/'] ?? 'welcome';
}

type AppState = {
  step: Step;
  persona: Persona | null;
  profile: Profile | null;
  portfolio: Portfolio | null;
  feed: FeedResponse | null;
  consideration: Consideration | null;
  considerFeed: FeedResponse | null; // résultat du test d'achat : ne modifie jamais le fil principal
  limitsOpen: boolean;
};

type AppActions = {
  go: (step: Step) => void;
  choosePersona: (persona: Persona) => void;
  setProfile: (profile: Profile) => void;
  setPortfolio: (portfolio: Portfolio | null) => void;
  setFeed: (feed: FeedResponse | null) => void;
  setConsiderResult: (consideration: Consideration | null, feed: FeedResponse | null) => void;
  setLimitsOpen: (open: boolean) => void;
  reset: () => void;
};

const initial: AppState = {
  step: 'welcome', persona: null, profile: null, portfolio: null, feed: null,
  consideration: null, considerFeed: null, limitsOpen: false,
};

/** Un écran est-il accessible avec l'état actuel? Sinon on revient à l'étape utile. */
function guard(step: Step, s: AppState): Step {
  if (step === 'profile' && !s.profile) return 'welcome';
  if (step === 'portfolio' && !s.profile) return 'welcome';
  if (DASHBOARD_TABS.includes(step) && (!s.profile || !s.portfolio)) return s.profile ? 'portfolio' : 'welcome';
  return step;
}

const Ctx = createContext<(AppState & AppActions) | null>(null);

export function AppProvider({ children, initialState }: { children: ReactNode; initialState?: Partial<AppState> }) {
  const [state, setState] = useState<AppState>({ ...initial, ...initialState });
  const patch = useCallback((p: Partial<AppState>) => setState((s) => ({ ...s, ...p })), []);

  // Hash -> étape (bouton Retour/Avancer du navigateur, lien direct).
  useEffect(() => {
    const onHash = () => setState((s) => ({ ...s, step: guard(stepFromHash(window.location.hash), s) }));
    onHash();
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const actions = useMemo<AppActions>(
    () => ({
      go: (step) => {
        setState((s) => ({ ...s, step: guard(step, s) }));
        if (window.location.hash !== HASH[step]) window.location.hash = HASH[step];
        window.scrollTo?.(0, 0);
      },
      choosePersona: (persona) => {
        patch({ persona, profile: persona.profile, portfolio: null, feed: null, consideration: null, considerFeed: null, step: 'profile' });
        window.location.hash = HASH.profile;
      },
      setProfile: (profile) => patch({ profile, feed: null, consideration: null, considerFeed: null }),
      setPortfolio: (portfolio) => patch({ portfolio, feed: null, consideration: null, considerFeed: null }),
      setFeed: (feed) => patch({ feed }),
      setConsiderResult: (consideration, considerFeed) => patch({ consideration, considerFeed }),
      setLimitsOpen: (limitsOpen) => patch({ limitsOpen }),
      reset: () => {
        setState(initial);
        window.location.hash = HASH.welcome;
      },
    }),
    [patch],
  );

  return <Ctx.Provider value={{ ...state, ...actions }}>{children}</Ctx.Provider>;
}

export function useApp() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useApp doit être utilisé dans <AppProvider>');
  return v;
}

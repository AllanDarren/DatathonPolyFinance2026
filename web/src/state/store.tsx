// État en mémoire uniquement (aucun localStorage, aucun cookie).
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import type { FeedResponse, Persona, Portfolio, Profile } from '../types/contracts';

export type Step = 'welcome' | 'questionnaire' | 'profile' | 'portfolio' | 'dashboard' | 'compare';

type AppState = {
  step: Step;
  persona: Persona | null;
  profile: Profile | null;
  portfolio: Portfolio | null;
  feed: FeedResponse | null;
  limitsOpen: boolean;
};

type AppActions = {
  go: (step: Step) => void;
  choosePersona: (persona: Persona) => void;
  setProfile: (profile: Profile) => void;
  setPortfolio: (portfolio: Portfolio | null) => void;
  setFeed: (feed: FeedResponse | null) => void;
  setLimitsOpen: (open: boolean) => void;
  reset: () => void;
};

const initial: AppState = { step: 'welcome', persona: null, profile: null, portfolio: null, feed: null, limitsOpen: false };

const Ctx = createContext<(AppState & AppActions) | null>(null);

export function AppProvider({ children, initialState }: { children: ReactNode; initialState?: Partial<AppState> }) {
  const [state, setState] = useState<AppState>({ ...initial, ...initialState });
  const patch = useCallback((p: Partial<AppState>) => setState((s) => ({ ...s, ...p })), []);

  const actions = useMemo<AppActions>(
    () => ({
      go: (step) => {
        patch({ step });
        window.scrollTo?.(0, 0);
      },
      choosePersona: (persona) => patch({ persona, profile: persona.profile, portfolio: null, feed: null, step: 'profile' }),
      setProfile: (profile) => patch({ profile, feed: null }),
      setPortfolio: (portfolio) => patch({ portfolio, feed: null }),
      setFeed: (feed) => patch({ feed }),
      setLimitsOpen: (limitsOpen) => patch({ limitsOpen }),
      reset: () => setState(initial),
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

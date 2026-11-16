// Synchronisation du compte : à la connexion, on recharge le profil, le portefeuille et le dernier brief ;
// ensuite, chaque nouveau profil, portefeuille déposé ou brief calculé est sauvegardé (DynamoDB + S3).
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { api } from '../api/client';
import { meApi } from '../api/me';
import { useAuth } from '../auth/AuthProvider';
import type { FeedResponse, Portfolio, Profile } from '../types/contracts';
import type { BriefMeta } from '../types/user';
import { useApp } from './store';

type AccountValue = {
  ready: boolean; // compte chargé (ou aucun utilisateur connecté)
  loadError: unknown;
  syncError: unknown;
  briefs: BriefMeta[];
  openBrief: (id: string) => Promise<void>;
  retry: () => void;
};

const Ctx = createContext<AccountValue | null>(null);

const newer = (a: string | null | undefined, b: string | null | undefined) => !a || !b || a >= b;

export function AccountProvider({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const app = useApp();
  const [ready, setReady] = useState(false);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [syncError, setSyncError] = useState<unknown>(null);
  const [briefs, setBriefs] = useState<BriefMeta[]>([]);
  const [attempt, setAttempt] = useState(0);
  // Dernières valeurs connues du serveur : on ne réécrit que ce qui a changé.
  const saved = useRef<{ profile: Profile | null; csv: string | null; feed: FeedResponse | null }>({ profile: null, csv: null, feed: null });
  const appRef = useRef(app);
  appRef.current = app;

  const sub = auth.status === 'signedIn' ? auth.user?.sub ?? null : null;

  // Chargement du compte à la connexion.
  useEffect(() => {
    if (auth.status !== 'signedIn') {
      setReady(auth.status === 'signedOut');
      setBriefs([]);
      saved.current = { profile: null, csv: null, feed: null };
      return;
    }
    let alive = true;
    setReady(false);
    setLoadError(null);
    (async () => {
      const token = await auth.getAccessToken();
      if (!token) return;
      const me = await meApi.get(token);
      const local = appRef.current;
      let feed: FeedResponse | null = null;
      const last = me.briefs[0];
      if (me.profile && me.portfolio && last && newer(last.saved_at, me.profile_updated_at) && newer(last.saved_at, me.portfolio_updated_at)) {
        feed = await meApi.getBrief(token, last.brief_id).catch(() => null);
      }
      const personas = me.persona_id ? await api.getPersonas().catch(() => []) : [];
      if (!alive) return;
      // Ce que l'utilisateur vient de choisir avant de se connecter l'emporte sur un compte vide.
      const profile = me.profile ?? local.profile;
      const portfolio: Portfolio | null = me.portfolio ?? local.portfolio;
      const csv = me.portfolio ? me.portfolio_csv : local.portfolioCsv;
      saved.current = { profile: me.profile, csv: me.portfolio ? me.portfolio_csv : null, feed };
      setBriefs(me.briefs);
      app.hydrate({
        persona: me.profile ? personas.find((p) => p.id === me.persona_id) ?? null : local.persona,
        profile, portfolio, portfolioCsv: csv, feed: feed ?? (me.profile ? null : local.feed),
      });
      setReady(true);
    })().catch((e: unknown) => {
      if (alive) setLoadError(e);
    });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.status, sub, attempt]);

  const withToken = useCallback(
    async (fn: (token: string) => Promise<void>) => {
      try {
        const token = await auth.getAccessToken();
        if (token) await fn(token);
        setSyncError(null);
      } catch (e) {
        setSyncError(e);
      }
    },
    [auth],
  );

  // Sauvegardes.
  const { profile, persona, portfolioCsv, feed } = app;
  useEffect(() => {
    if (!ready || !sub || !profile || profile === saved.current.profile) return;
    saved.current.profile = profile;
    const personaId = persona && persona.profile === profile ? persona.id : null;
    void withToken((tk) => meApi.saveProfile(tk, profile, personaId));
  }, [ready, sub, profile, persona, withToken]);

  useEffect(() => {
    if (!ready || !sub || !portfolioCsv || portfolioCsv === saved.current.csv) return;
    saved.current.csv = portfolioCsv;
    void withToken(async (tk) => {
      await meApi.savePortfolio(tk, portfolioCsv);
    });
  }, [ready, sub, portfolioCsv, withToken]);

  useEffect(() => {
    if (!ready || !sub || !feed || feed === saved.current.feed) return;
    saved.current.feed = feed;
    void withToken(async (tk) => {
      const meta = await meApi.saveBrief(tk, feed);
      setBriefs((b) => [meta, ...b].slice(0, 10));
    });
  }, [ready, sub, feed, withToken]);

  const openBrief = useCallback(
    async (id: string) => {
      await withToken(async (tk) => {
        const f = await meApi.getBrief(tk, id);
        saved.current.feed = f; // déjà sauvegardé : ne pas le recopier
        appRef.current.setFeed(f);
        appRef.current.go('feed');
      });
    },
    [withToken],
  );

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  return <Ctx.Provider value={{ ready, loadError, syncError, briefs, openBrief, retry }}>{children}</Ctx.Provider>;
}

export function useAccount(): AccountValue {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAccount doit être utilisé dans <AccountProvider>');
  return v;
}

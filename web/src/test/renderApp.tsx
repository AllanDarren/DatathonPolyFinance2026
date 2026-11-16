import { render } from '@testing-library/react';
import { App } from '../App';
import { resetMockAccounts } from '../api/mock/mockMe';
import { AuthProvider } from '../auth/AuthProvider';
import { localClient } from '../auth/local';
import { clearSession, saveSession } from '../auth/session';
import type { AuthClient } from '../auth/types';
import { AccountProvider } from '../state/account';
import { AppProvider } from '../state/store';

/** Rend l'application complète. `signedIn` ouvre une session de test (compte local vide). */
export function renderApp({ signedIn = true, client }: { signedIn?: boolean; client?: AuthClient } = {}) {
  window.location.hash = '';
  clearSession();
  resetMockAccounts();
  if (signedIn) saveSession({ email: 'test@exemple.com', sub: 'local-test' }, 'local-refresh.local-test', false);
  const auth = client ?? localClient();
  return render(
    <AuthProvider client={auth}>
      <AppProvider>
        <AccountProvider>
          <App />
        </AccountProvider>
      </AppProvider>
    </AuthProvider>,
  );
}

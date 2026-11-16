import { useAuth } from './auth/AuthProvider';
import { ErrorBox, Skeleton } from './components/Feedback';
import { Layout } from './components/Layout';
import { AuthScreen } from './screens/AuthScreen';
import { useAccount } from './state/account';
import { DashboardShell } from './screens/DashboardShell';
import { PortfolioImport } from './screens/PortfolioImport';
import { ProfileResult } from './screens/ProfileResult';
import { Questionnaire } from './screens/Questionnaire';
import { Welcome } from './screens/Welcome';
import { DASHBOARD_TABS, useApp } from './state/store';
import { t } from './strings';

function Screen() {
  const { step } = useApp();
  const auth = useAuth();
  const account = useAccount();
  // L'accueil est public ; tout le reste exige un compte (pour retrouver ses données à la reconnexion).
  if (step !== 'welcome') {
    if (auth.status === 'loading') return <Skeleton lines={3} label={t.auth.loadingAccount} />;
    if (auth.status !== 'signedIn') return <AuthScreen initialMode={step === 'login' ? 'signIn' : 'signUp'} />;
  }
  if (step !== 'welcome' && auth.status === 'signedIn' && !account.ready) {
    return account.loadError
      ? <ErrorBox error={account.loadError} onRetry={account.retry} />
      : <Skeleton lines={3} label={t.auth.loadingAccount} />;
  }
  if (DASHBOARD_TABS.includes(step)) return <DashboardShell tab={step} />;
  switch (step) {
    case 'questionnaire':
      return <Questionnaire />;
    case 'profile':
      return <ProfileResult />;
    case 'portfolio':
      return <PortfolioImport />;
    default:
      return <Welcome />;
  }
}

export function App() {
  return (
    <Layout>
      <Screen />
    </Layout>
  );
}

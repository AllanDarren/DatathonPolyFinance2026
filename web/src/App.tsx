import { Layout } from './components/Layout';
import { DashboardShell } from './screens/DashboardShell';
import { PortfolioImport } from './screens/PortfolioImport';
import { ProfileResult } from './screens/ProfileResult';
import { Questionnaire } from './screens/Questionnaire';
import { Welcome } from './screens/Welcome';
import { DASHBOARD_TABS, useApp } from './state/store';

function Screen() {
  const { step } = useApp();
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

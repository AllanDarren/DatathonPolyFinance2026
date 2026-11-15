import { Layout } from './components/Layout';
import { Compare } from './screens/Compare';
import { Dashboard } from './screens/Dashboard';
import { PortfolioImport } from './screens/PortfolioImport';
import { ProfileResult } from './screens/ProfileResult';
import { Questionnaire } from './screens/Questionnaire';
import { Welcome } from './screens/Welcome';
import { useApp } from './state/store';

function Screen() {
  const { step } = useApp();
  switch (step) {
    case 'welcome':
      return <Welcome />;
    case 'questionnaire':
      return <Questionnaire />;
    case 'profile':
      return <ProfileResult />;
    case 'portfolio':
      return <PortfolioImport />;
    case 'dashboard':
      return <Dashboard />;
    case 'compare':
      return <Compare />;
  }
}

export function App() {
  return (
    <Layout>
      <Screen />
    </Layout>
  );
}

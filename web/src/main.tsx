import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { AuthProvider } from './auth/AuthProvider';
import { AccountProvider } from './state/account';
import { AppProvider } from './state/store';
import './styles.css';
import './redesign.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <AppProvider>
        <AccountProvider>
          <App />
        </AccountProvider>
      </AppProvider>
    </AuthProvider>
  </StrictMode>,
);

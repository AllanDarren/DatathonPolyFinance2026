import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AUTH_MSG, cognitoError, validateCredentials } from '../auth/messages';
import { loadSession } from '../auth/session';
import { renderApp } from './renderApp';

const EMAIL = 'amira@exemple.com';
const PASSWORD = 'Secret123';

async function fillSignUp(user: ReturnType<typeof userEvent.setup>, email: string, pw: string, confirm = pw) {
  await user.clear(screen.getByLabelText('Courriel'));
  if (email) await user.type(screen.getByLabelText('Courriel'), email);
  await user.clear(screen.getByLabelText('Mot de passe'));
  if (pw) await user.type(screen.getByLabelText('Mot de passe'), pw);
  await user.clear(screen.getByLabelText('Confirme le mot de passe'));
  if (confirm) await user.type(screen.getByLabelText('Confirme le mot de passe'), confirm);
  await user.click(screen.getByRole('button', { name: 'Créer mon compte' }));
}

async function signIn(user: ReturnType<typeof userEvent.setup>, email: string, pw: string) {
  await user.clear(screen.getByLabelText('Courriel'));
  await user.type(screen.getByLabelText('Courriel'), email);
  await user.clear(screen.getByLabelText('Mot de passe'));
  await user.type(screen.getByLabelText('Mot de passe'), pw);
  await user.click(screen.getByRole('button', { name: 'Se connecter' }));
}

describe('compte', () => {
  it('créer un compte → portefeuille → déconnexion → reconnexion : tout est retrouvé', async () => {
    renderApp({ signedIn: false });
    const user = userEvent.setup();

    // Un écran protégé demande un compte.
    await user.click(await screen.findByRole('button', { name: /Charger Robert/ }));
    expect(await screen.findByRole('heading', { name: 'Crée ton compte' })).toBeInTheDocument();

    // Champs vides, mots de passe différents, mot de passe faible : messages en français.
    await fillSignUp(user, '', '');
    expect(await screen.findByRole('alert')).toHaveTextContent(AUTH_MSG.emailRequired);
    await fillSignUp(user, EMAIL, PASSWORD, 'Autre1234');
    expect(await screen.findByRole('alert')).toHaveTextContent(AUTH_MSG.passwordMismatch);
    await fillSignUp(user, EMAIL, 'court');
    expect(await screen.findByRole('alert')).toHaveTextContent(AUTH_MSG.passwordWeak);

    await fillSignUp(user, EMAIL, PASSWORD);
    // Le profil choisi avant l'inscription est gardé.
    expect(await screen.findByRole('heading', { name: /Ton profil/ })).toBeInTheDocument();
    expect(loadSession()?.remember).toBe(true); // « rester connecté » coché par défaut

    await user.click(screen.getByRole('button', { name: /Continuer vers le portefeuille/ }));
    await user.click(screen.getByRole('button', { name: /portefeuille d’exemple de Robert/ }));
    await screen.findByText('XBB.TO');
    await user.click(screen.getByRole('button', { name: /Voir mon tableau de bord/ }));
    await waitFor(() => expect(window.location.hash).toBe('#/apercu'));

    // Déconnexion : session effacée, retour à l'accueil.
    await user.click(await screen.findByRole('button', { name: /Menu du profil/ }));
    await user.click(screen.getByRole('menuitem', { name: 'Déconnexion' }));
    expect(await screen.findByRole('button', { name: /Charger Robert/ })).toBeInTheDocument();
    expect(loadSession()).toBeNull();

    // Reconnexion : mauvais mot de passe, puis le bon.
    await user.click(screen.getAllByRole('button', { name: 'Se connecter' })[0]!);
    expect(await screen.findByRole('heading', { name: 'Content de te revoir' })).toBeInTheDocument();
    await signIn(user, EMAIL, 'Mauvais123');
    expect(await screen.findByRole('alert')).toHaveTextContent(AUTH_MSG.badCredentials);
    await signIn(user, EMAIL, PASSWORD);

    // Retour direct au tableau de bord, avec le même portefeuille et le même profil.
    await waitFor(() => expect(window.location.hash).toBe('#/apercu'));
    expect(await screen.findAllByText('XBB.TO')).not.toHaveLength(0);
    await user.click(await screen.findByRole('button', { name: /Menu du profil/ }));
    await user.click(screen.getByRole('menuitem', { name: 'Mon profil' }));
    expect(await screen.findByRole('heading', { name: /Ton profil/ })).toBeInTheDocument();
    expect(await screen.findByText('Mes derniers briefs')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Ouvrir' })).toBeInTheDocument(); // le brief calculé a été gardé
  });

  it('un courriel déjà utilisé est refusé', async () => {
    renderApp({ signedIn: false });
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: /Charger Robert/ }));
    await screen.findByRole('heading', { name: 'Crée ton compte' });
    await fillSignUp(user, EMAIL, PASSWORD);
    await screen.findByRole('heading', { name: /Ton profil/ });
    await user.click(screen.getByRole('button', { name: /Menu du profil/ }));
    await user.click(screen.getByRole('menuitem', { name: 'Déconnexion' }));
    await user.click(await screen.findByRole('button', { name: /Commencer/ }));
    await screen.findByRole('heading', { name: 'Crée ton compte' });
    await fillSignUp(user, EMAIL.toUpperCase(), PASSWORD);
    expect(await screen.findByRole('alert')).toHaveTextContent(AUTH_MSG.emailTaken);
  });
});

describe('messages d’authentification', () => {
  it('valide les champs avant tout appel', () => {
    expect(validateCredentials('', 'x')).toBe(AUTH_MSG.emailRequired);
    expect(validateCredentials('pas-un-courriel', 'x')).toBe(AUTH_MSG.emailInvalid);
    expect(validateCredentials('a@b.ca', '')).toBe(AUTH_MSG.passwordRequired);
    expect(validateCredentials('a@b.ca', 'Secret123', 'Secret123')).toBeNull();
  });

  it('traduit les erreurs Cognito', () => {
    expect(cognitoError('UsernameExistsException').message).toBe(AUTH_MSG.emailTaken);
    expect(cognitoError('NotAuthorizedException').message).toBe(AUTH_MSG.badCredentials);
    expect(cognitoError('InvalidPasswordException').message).toBe(AUTH_MSG.passwordWeak);
    expect(cognitoError('TooManyRequestsException').message).toBe(AUTH_MSG.tooMany);
  });
});

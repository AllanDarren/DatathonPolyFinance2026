import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../App';
import { AppProvider } from '../state/store';

function setup() {
  render(<AppProvider><App /></AppProvider>);
  return userEvent.setup();
}

describe('parcours', () => {
  it('l’avertissement de simulation est toujours visible', () => {
    setup();
    expect(screen.getAllByText(/pas un conseil financier/).length).toBeGreaterThan(0);
  });

  it('Robert : persona → profil → portefeuille → fil, avec « Pourquoi? »', async () => {
    const user = setup();
    await user.click(await screen.findByRole('button', { name: /Charger Robert/ }));
    expect(screen.getByRole('heading', { name: /Ton profil/ })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Continuer vers le portefeuille/ }));
    await user.click(screen.getByRole('button', { name: /portefeuille d’exemple de Robert/ }));
    expect(await screen.findByText('XBB.TO')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Voir mon tableau de bord/ }));
    expect(await screen.findByText(/Fortis déclare son dividende/, {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getAllByText('exemple fictif').length).toBeGreaterThan(0);

    const card = screen.getByText(/Fortis déclare son dividende/).closest('article')!;
    await user.click(within(card).getByRole('button', { name: 'Pourquoi?' }));
    expect(within(card).getByText('Règles déclenchées')).toBeInTheDocument();
    expect(within(card).getAllByText('Fait').length).toBeGreaterThan(0);
    expect(within(card).getByText(/Vérifiée par le gardien/)).toBeInTheDocument();

    // Preuve cliquable
    await user.click(within(card).getAllByRole('button', { name: /Voir la preuve/ })[0]!);
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
  });

  it('aucun verbe d’ordre dans l’interface', async () => {
    setup();
    await screen.findByRole('button', { name: /Charger Robert/ });
    expect(document.body.textContent ?? '').not.toMatch(/\b(achète|vends|tu devrais)\b/i);
  });
});

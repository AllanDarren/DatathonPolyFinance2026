import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../App';
import { AppProvider } from '../state/store';

function setup() {
  window.location.hash = ''; // chaque test repart de l'accueil (la navigation passe par le hash)
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
    // le tiroir « Pourquoi? » et le tiroir de la preuve sont ouverts l'un sur l'autre
    expect((await screen.findAllByRole('dialog')).length).toBe(2);
  });

  it('onglets : « Tester un achat » montre verdict, gouvernance et trace des agents, sans toucher au fil', async () => {
    const user = setup();
    await user.click(await screen.findByRole('button', { name: /Charger Robert/ }));
    await user.click(screen.getByRole('button', { name: /Continuer vers le portefeuille/ }));
    await user.click(screen.getByRole('button', { name: /portefeuille d’exemple de Robert/ }));
    await screen.findByText('XBB.TO');
    await user.click(screen.getByRole('button', { name: /Voir mon tableau de bord/ }));
    await screen.findByText(/Fortis déclare son dividende/, {}, { timeout: 3000 });
    expect(window.location.hash).toBe('#/fil');

    await user.click(screen.getByRole('link', { name: /Tester un achat/ }));
    expect(window.location.hash).toBe('#/tester');
    await user.click(screen.getByRole('button', { name: /NVDA 20 %/ }));
    expect((await screen.findAllByText(/Incohérent avec ton profil/, {}, { timeout: 3000 })).length).toBeGreaterThan(0);
    expect(screen.getByText('Contrôles de gouvernance')).toBeInTheDocument();
    expect(screen.getByText('Comment les agents ont travaillé')).toBeInTheDocument();

    // retour au fil : il n'a pas été remplacé par le test d'achat
    await user.click(screen.getByRole('link', { name: /Mes nouvelles/ }));
    expect(await screen.findByText(/Fortis déclare son dividende/)).toBeInTheDocument();
  });

  it('questionnaire : la note libre propose des préférences à confirmer', async () => {
    const user = setup();
    await user.click(await screen.findByRole('button', { name: /Répondre au questionnaire/ }));
    await screen.findByRole('button', { name: 'Suivante' });
    // première option de chaque question jusqu'à la note
    for (;;) {
      const next = screen.queryByRole('button', { name: 'Suivante' });
      if (!next) break;
      const radios = screen.queryAllByRole('radio');
      if (radios.length) await user.click(radios[0]!);
      await user.click(next);
      if (screen.queryByRole('textbox')) break;
    }
    await user.type(screen.getByRole('textbox', { name: /Autre chose/ }), 'Je veux éviter le pétrole');
    await user.click(screen.getByRole('button', { name: 'Analyser ma note' }));
    expect(await screen.findByText(/Combustibles fossiles/)).toBeInTheDocument();
    expect(screen.getByText(/« pétrole »/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Voir mon profil' }));
    expect(await screen.findByText(/Préférences tirées de ta note/)).toBeInTheDocument();
  });

  it('aucun verbe d’ordre dans l’interface', async () => {
    setup();
    await screen.findByRole('button', { name: /Charger Robert/ });
    expect(document.body.textContent ?? '').not.toMatch(/\b(achète|vends|tu devrais)\b/i);
  });
});

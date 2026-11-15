import { useRef, useState, type DragEvent } from 'react';
import { api } from '../api/client';
import { UserError } from '../api/errors';
import { ErrorBox, Skeleton } from '../components/Feedback';
import { formatCad, formatPct } from '../lib/format';
import { useApp } from '../state/store';
import { t } from '../strings';

const TEMPLATE = 'ticker,montant\nXBB.TO,10000\nRY.TO,5000\nSPY,5000\n';
const TEMPLATE_HREF = `data:text/csv;charset=utf-8,${encodeURIComponent(TEMPLATE)}`;

export function PortfolioImport() {
  const { persona, portfolio, setPortfolio, go } = useApp();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function parse(csv: string) {
    setBusy(true);
    setError(null);
    try {
      setPortfolio(await api.parsePortfolio(csv));
    } catch (e) {
      setPortfolio(null);
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function onFile(file: File | undefined) {
    if (!file) return;
    if (!/\.csv$/i.test(file.name) && !file.type.includes('csv') && !file.type.startsWith('text/')) {
      setError(new UserError(t.portfolio.invalidFile));
      return;
    }
    await parse(await file.text());
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDrag(false);
    void onFile(e.dataTransfer.files[0]);
  }

  return (
    <section className="panel" aria-labelledby="pf-title">
      <h1 id="pf-title">{t.portfolio.title}</h1>
      <p className="lead">{t.portfolio.lead}</p>
      <div className="import-grid">
        <div
          className={`dropzone ${drag ? 'dropzone-on' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
        >
          <p><strong>{t.portfolio.drop}</strong></p>
          <p className="muted">{t.portfolio.or}</p>
          <button type="button" className="btn btn-secondary" onClick={() => inputRef.current?.click()}>{t.portfolio.browse}</button>
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            aria-label={t.portfolio.browse}
            onChange={(e) => void onFile(e.target.files?.[0])}
          />
          <a className="small" href={TEMPLATE_HREF} download="portefeuille_gabarit.csv">
            {t.portfolio.template}
          </a>
        </div>
        {persona && (
          <div className="sample">
            <button type="button" className="btn btn-primary" onClick={() => void parse(persona.sample_portfolio_csv)}>
              {t.portfolio.useSample(persona.profile.label)}
            </button>
          </div>
        )}
      </div>
      <p className="small muted"><span aria-hidden="true">🔒 </span>{t.portfolio.privacy}</p>

      {busy && <Skeleton lines={4} label={t.portfolio.parsing} />}
      {error ? <ErrorBox error={error} /> : null}

      {portfolio && !busy && (
        <div className="preview">
          <h2 className="h-small">{t.portfolio.preview}</h2>
          {portfolio.unanalyzed.weight > 0 && (
            <div className="callout callout-warn" role="note">
              <span aria-hidden="true">⚠ </span>
              {t.portfolio.unanalyzed(formatPct(portfolio.unanalyzed.weight), portfolio.unanalyzed.tickers.join(', '))}
            </div>
          )}
          {portfolio.warnings.length > 0 && (
            <div className="callout" role="note">
              <strong>{t.portfolio.warnings}</strong>
              <ul>{portfolio.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
            </div>
          )}
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t.portfolio.ticker}</th>
                <th scope="col">{t.portfolio.assetClass}</th>
                <th scope="col" className="num">{t.portfolio.amount}</th>
                <th scope="col" className="num">{t.portfolio.weight}</th>
              </tr>
            </thead>
            <tbody>
              {portfolio.positions.map((p) => (
                <tr key={p.ticker}>
                  <td className="ticker">{p.ticker}</td>
                  <td>{t.labels.assetClass[p.asset_class] ?? p.asset_class}</td>
                  <td className="num">{formatCad(p.amount)}</td>
                  <td className="num">{formatPct(p.weight)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row" colSpan={2}>{t.portfolio.total}</th>
                <td className="num">{formatCad(portfolio.total_amount)}</td>
                <td />
              </tr>
            </tfoot>
          </table>
          <div className="row-end">
            <button type="button" className="btn btn-primary" onClick={() => go('feed')}>{t.portfolio.continue}</button>
          </div>
        </div>
      )}
    </section>
  );
}

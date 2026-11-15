import { Term } from '../components/Term';
import { formatPct } from '../lib/format';
import { useApp } from '../state/store';
import { t } from '../strings';

export function ProfileResult() {
  const { profile, go } = useApp();
  if (!profile) return null;
  const p = profile;
  const L = t.labels;

  return (
    <section className="panel narrow" aria-labelledby="profile-title">
      <h1 id="profile-title">{t.profile.title}</h1>
      <p className="muted small">{t.profile.computedByRules}</p>
      <dl className="facts">
        <div><dt><Term id="horizon">{t.profile.horizon}</Term></dt><dd>{t.profile.horizonValue(p.horizon_years)} ({L.horizonBucket[p.horizon_bucket]})</dd></div>
        <div><dt>{t.profile.risk}</dt><dd>{L.risk[p.risk_tolerance]}</dd></div>
        <div><dt>{t.profile.maxLoss}</dt><dd>{formatPct(p.max_acceptable_loss_pct, 0)}</dd></div>
        <div><dt>{t.profile.objective}</dt><dd>{L.objective[p.objective]}</dd></div>
        <div><dt>{t.profile.experience}</dt><dd>{L.experience[p.experience]}</dd></div>
      </dl>
      <h2 className="h-small">{t.profile.limitsTitle}</h2>
      <dl className="facts">
        <div><dt>{t.profile.maxSingle}</dt><dd>{formatPct(p.limits.max_single_position, 0)}</dd></div>
        <div><dt><Term id="volatility">{t.profile.maxHighVol}</Term></dt><dd>{formatPct(p.limits.max_high_vol_share, 0)}</dd></div>
      </dl>
      <h2 className="h-small">{t.profile.preferences}</h2>
      <dl className="facts">
        <div><dt>{t.profile.avoidControversies}</dt><dd>{p.preferences.avoid_controversies ? 'oui' : 'non'}</dd></div>
        <div><dt>{t.profile.excluded}</dt><dd>{p.preferences.excluded_sectors.join(', ') || t.profile.none}</dd></div>
        <div><dt>{t.profile.interests}</dt><dd>{p.preferences.interests.join(', ') || t.profile.none}</dd></div>
      </dl>
      {p.inconsistencies.length > 0 && (
        <div className="callout callout-warn" role="note">
          <strong><span aria-hidden="true">⚠ </span>{t.profile.inconsistenciesTitle}</strong>
          <ul>{p.inconsistencies.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </div>
      )}
      <div className="row-end">
        <button type="button" className="btn btn-primary" onClick={() => go('portfolio')}>{t.profile.continue}</button>
      </div>
    </section>
  );
}

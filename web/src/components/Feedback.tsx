import { userMessage } from '../api/errors';
import { t } from '../strings';

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="error-box" role="alert">
      <span aria-hidden="true">⚠</span>
      <p>{userMessage(error)}</p>
      {onRetry && (
        <button type="button" className="btn btn-secondary" onClick={onRetry}>
          {t.errors.retry}
        </button>
      )}
    </div>
  );
}

export function Skeleton({ lines = 3, label }: { lines?: number; label: string }) {
  return (
    <div className="skeleton" role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      <p className="skeleton-label" aria-hidden="true">{label}</p>
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton-line" style={{ width: `${90 - i * 12}%` }} aria-hidden="true" />
      ))}
    </div>
  );
}

export function SyntheticBadge() {
  return (
    <span className="badge badge-synthetic" title="Ce titre n’est pas une vraie nouvelle.">
      <span aria-hidden="true">✎</span> {t.syntheticBadge}
    </span>
  );
}

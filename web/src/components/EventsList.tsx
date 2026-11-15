import type { Event } from '../types/contracts';
import { formatDate } from '../lib/format';
import { t } from '../strings';

export function EventsList({ events }: { events: Event[] }) {
  if (events.length === 0) return <p className="muted">{t.events.empty}</p>;
  const sorted = [...events].sort((a, b) => a.date.localeCompare(b.date));
  return (
    <ol className="events">
      {sorted.map((e) => (
        <li key={e.id} className="event">
          <time className="event-date" dateTime={e.date}>{formatDate(e.date)}</time>
          <div className="event-body">
            <span className="event-title">{e.title}</span>
            <span className="event-meta">
              <span className="badge badge-cat">{t.events.types[e.type]}</span>
              {e.tickers.map((tk) => <span key={tk} className="ticker">{tk}</span>)}
              <span className={`badge ${e.is_estimated ? 'badge-estimated' : 'badge-confirmed'}`}>
                <span aria-hidden="true">{e.is_estimated ? '≈ ' : '✔ '}</span>
                {e.is_estimated ? t.events.estimated : t.events.confirmed}
              </span>
            </span>
            <span className="small muted">{e.source}</span>
          </div>
        </li>
      ))}
    </ol>
  );
}

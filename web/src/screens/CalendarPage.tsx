// Onglet « Calendrier » : événements à venir (résultats, dividendes, taux), groupés par mois et filtrables.
import { useMemo, useState } from 'react';
import { EventsList } from '../components/EventsList';
import { t } from '../strings';
import type { EventType, FeedResponse } from '../types/contracts';

const monthFmt = new Intl.DateTimeFormat('fr-CA', { year: 'numeric', month: 'long', timeZone: 'UTC' });

export function CalendarPage({ feed }: { feed: FeedResponse }) {
  const [type, setType] = useState<'' | EventType>('');
  const events = feed.events.filter((e) => !type || e.type === type);
  const months = useMemo(() => {
    const m = new Map<string, typeof events>();
    for (const e of [...events].sort((a, b) => a.date.localeCompare(b.date))) {
      const k = e.date.slice(0, 7);
      m.set(k, [...(m.get(k) ?? []), e]);
    }
    return [...m];
  }, [events]);
  const types = [...new Set(feed.events.map((e) => e.type))];

  return (
    <section className="calendar" aria-labelledby="cal-title">
      <div className="panel">
        <h2 id="cal-title">{t.events.title}</h2>
        <p className="muted small">{t.events.lead}</p>
        <div className="filters" role="group" aria-label={t.dashboard.filters}>
          <select aria-label="Filtrer par type" value={type} onChange={(e) => setType(e.target.value as '' | EventType)}>
            <option value="">{t.events.allTypes}</option>
            {types.map((x) => <option key={x} value={x}>{t.events.types[x]}</option>)}
          </select>
        </div>
      </div>
      {months.length === 0 ? (
        <p className="muted">{t.events.empty}</p>
      ) : (
        months.map(([k, list]) => (
          <section key={k} className="panel" aria-label={monthFmt.format(new Date(`${k}-01T00:00:00Z`))}>
            <h3 className="h-small">{monthFmt.format(new Date(`${k}-01T00:00:00Z`))}</h3>
            <EventsList events={list} />
          </section>
        ))
      )}
    </section>
  );
}

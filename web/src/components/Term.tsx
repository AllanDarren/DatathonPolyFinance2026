// Terme du glossaire avec définition au survol et au clavier (rules/glossary.yaml).
import { useId, type ReactNode } from 'react';
import glossaryJson from '../generated/glossary.json';
import type { Glossary } from '../types/contracts';

const GLOSSARY = new Map((glossaryJson as Glossary).terms.map((g) => [g.id, g]));

export function Term({ id, children }: { id: string; children?: ReactNode }) {
  const tipId = useId();
  const entry = GLOSSARY.get(id);
  if (!entry) return <>{children}</>;
  return (
    <span className="term" tabIndex={0} aria-describedby={tipId}>
      {children ?? entry.term}
      <span role="tooltip" id={tipId} className="term-tip">
        <strong>{entry.term}</strong> : {entry.definition_fr}
      </span>
    </span>
  );
}

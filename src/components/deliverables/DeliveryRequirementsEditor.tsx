import { useId } from 'react';
import { Textarea } from '@/components/ui/textarea';
import type { ArtifactGenerateInput } from '@/features/deliverables/artifactApi';

export function parseDeliveryCriteria(facts: string, forbidden: string) {
  const lines = (value: string) => [...new Set(value.split('\n').map((line) => line.trim()).filter(Boolean))];
  const required = lines(facts);
  const banned = lines(forbidden);
  const valid = required.length <= 24 && banned.length <= 20
    && [...required, ...banned].every((line) => line.length >= 2 && line.length <= 300);
  return { valid, value: {
    required_facts: required.map((text) => ({ topic: text.slice(0, 160), expected_text: text, evidence_required: true })),
    forbidden_claims: banned,
  } };
}

export function DeliveryRequirementsEditor({ onChange, draft, onDraftChange }: {
  onChange: (value: ArtifactGenerateInput['delivery_requirements'], valid: boolean) => void;
  draft: { facts: string; forbidden: string };
  onDraftChange: (draft: { facts: string; forbidden: string }) => void;
}) {
  const id = useId();
  const { facts, forbidden } = draft;
  const parsed = parseDeliveryCriteria(facts, forbidden);
  const change = (nextFacts: string, nextForbidden: string) => {
    onDraftChange({ facts: nextFacts, forbidden: nextForbidden });
    const result = parseDeliveryCriteria(nextFacts, nextForbidden);
    onChange(result.value, result.valid);
  };
  return <details className="border-b px-6 py-4">
    <summary className="cursor-pointer text-xs font-medium">验收要求</summary>
    <div className="mt-4 grid gap-3 md:grid-cols-2">
      <label htmlFor={`${id}-facts`} className="space-y-2 text-xs">关键事实<Textarea id={`${id}-facts`} value={facts} maxLength={7224} onChange={(event) => change(event.target.value, forbidden)} className="min-h-24" /></label>
      <label htmlFor={`${id}-banned`} className="space-y-2 text-xs">禁止承诺<Textarea id={`${id}-banned`} value={forbidden} maxLength={6020} onChange={(event) => change(facts, event.target.value)} className="min-h-24" /></label>
    </div>
    {!parsed.valid && <p role="alert" className="mt-2 text-xs text-destructive">关键事实最多 24 项，禁止承诺最多 20 项，每项 2–300 字。</p>}
  </details>;
}

import { useEffect, useRef, useState } from 'react';
import type { TrafficMetricValueOut } from '@/types/api';
import { fmtNum, toNum } from '@/lib/num';

interface MetricCellProps {
  value: TrafficMetricValueOut | undefined;
  editable: boolean;
  targetLabel: string;
  onSave: (input: { value: number | null; note?: string | null }) => void;
}

// A single week cell. Double-click to edit: number input + optional note.
// The traffic-light color is computed server-side (value vs. weekly target):
// green pill = 达标, red pill = 未达标. Both share the same translucent-bg +
// colored-text idiom. Unfilled weeks render grey.
export default function MetricCell({ value, editable, targetLabel, onSave }: MetricCellProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const committingRef = useRef(false);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const startEdit = () => {
    if (!editable) return;
    const current = toNum(value?.value);
    setDraft(current === null ? '' : String(current));
    committingRef.current = false;
    setEditing(true);
  };

  const commit = () => {
    if (committingRef.current) return;
    committingRef.current = true;
    const trimmed = draft.trim();
    const num = trimmed === '' ? null : Number(trimmed);
    if (num !== null && !Number.isFinite(num)) {
      setEditing(false);
      return;
    }
    onSave({ value: num, note: value?.note ?? null });
    setEditing(false);
  };

  const num = toNum(value?.value);
  const hasValue = num !== null;
  const missed = value?.status === 'missed';

  return (
    <td
      onDoubleClick={startEdit}
      title={editable ? '双击录入' : undefined}
      className={`h-[86px] px-2 py-2 text-center align-middle ${editable ? 'cursor-pointer hover:bg-[var(--theme-accent-soft)]' : ''} transition-colors`}
    >
      <div className="flex h-8 items-center justify-center">
        {editing ? (
          <input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                commit();
              }
              if (e.key === 'Escape') {
                committingRef.current = true;
                setEditing(false);
              }
            }}
            inputMode="decimal"
            className="h-8 w-14 rounded-xl border-0 bg-[#eaf2ff] px-2 text-center font-mono text-[13px] text-slate-950 outline-none ring-0 focus:bg-[#e5efff]"
          />
        ) : hasValue && missed ? (
          <span className="inline-flex h-8 min-w-10 items-center justify-center rounded-full bg-red-50 px-3 font-mono text-[13px] text-red-600">
            {fmtNum(num)}
          </span>
        ) : hasValue ? (
          <span className="inline-flex h-8 min-w-10 items-center justify-center rounded-full bg-emerald-50 px-3 font-mono text-[13px] text-emerald-600">
            {fmtNum(num)}
          </span>
        ) : (
          <span className="text-[12px] font-semibold text-[var(--theme-accent)]">{editable ? '+ 录入' : '—'}</span>
        )}
      </div>
      <div className="mt-1 h-4 text-[10px] leading-4 text-[#7890ad]">
        {targetLabel}
      </div>
      {value?.note && !editing && (
        <div className="mx-auto mt-0.5 max-w-[110px] truncate text-[9px] leading-3 text-zinc-400">
          {value.note}
        </div>
      )}
    </td>
  );
}

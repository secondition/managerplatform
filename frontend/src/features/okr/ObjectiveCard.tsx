import { useEffect, useState, type FormEvent } from 'react';
import { GripVertical, MessageSquare, Plus, X } from 'lucide-react';
import type { KeyResultOut, ObjectiveOut } from '@/types/api';
import type { KeyResultInput } from '@/api/okr';
import { dayjs } from '@/lib/date';
import { toNum } from '@/lib/num';
import {
  useDeleteObjective,
  useUpdateObjective,
  useAddKeyResult,
  useUpdateKeyResult,
  useDeleteKeyResult,
  useCreateKeyResultProgress,
  useReorderKeyResults,
} from './hooks';
import OkrCommentsPanel from './OkrCommentsPanel';

function pct(value: unknown): number {
  const number = toNum(value);
  if (number === null) return 0;
  return Math.max(0, Math.min(100, Math.round(number)));
}

export default function ObjectiveCard({ index, month, objective, onMove, isDragging, draggingId, onDragStart, onDragEnd, onDropOrder }: { index: number; month: string; objective: ObjectiveOut; onMove: (targetId: number, before: boolean) => void; isDragging: boolean; draggingId: number | null; onDragStart: () => void; onDragEnd: () => void; onDropOrder: (ids: number[]) => void }) {
  const [editingObjective, setEditingObjective] = useState(false);
  const [addingKr, setAddingKr] = useState(false);
  const [draggingKrId, setDraggingKrId] = useState<number | null>(null);
  const [previewKrIds, setPreviewKrIds] = useState<number[] | null>(null);
  const [title, setTitle] = useState(objective.title);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const updateObjective = useUpdateObjective(month);
  const deleteObjective = useDeleteObjective(month);
  const addKeyResult = useAddKeyResult(month);
  const reorderKeyResults = useReorderKeyResults(month);
  const progress = pct(objective.progress);

  useEffect(() => {
    setTitle(objective.title);
  }, [objective.title]);

  const saveObjective = () => {
    const value = title.trim();
    if (!value || updateObjective.isPending) return;
    updateObjective.mutate(
      { id: objective.id, input: { title: value } },
      { onSuccess: () => setEditingObjective(false) },
    );
  };

  const cancelObjectiveEdit = () => {
    setTitle(objective.title);
    setEditingObjective(false);
  };

  return (
    <section data-okr-objective-id={objective.id} className={`workspace-card overflow-hidden transition-opacity duration-150 ${isDragging ? 'opacity-0' : 'opacity-100'}`} draggable onDragStart={(event) => { event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/okr-objective', String(objective.id)); onDragStart(); }} onDragEnd={onDragEnd} onDragOver={(event) => {
      event.preventDefault();
      const sourceId = Number(event.dataTransfer.getData('text/okr-objective')) || draggingId;
      if (sourceId && sourceId !== objective.id) {
        onMove(sourceId, event.clientY < event.currentTarget.getBoundingClientRect().top + event.currentTarget.getBoundingClientRect().height / 2);
      }
    }} onDrop={(event) => {
      event.preventDefault();
      const sourceId = Number(event.dataTransfer.getData('text/okr-objective')) || draggingId;
      if (sourceId) {
        const ids = document.querySelectorAll<HTMLElement>('[data-okr-objective-id]');
        onDropOrder(Array.from(ids).map((item) => Number(item.dataset.okrObjectiveId)).filter(Boolean));
      }
    }}>
      <div className="flex min-h-[48px] items-center gap-2.5 border-b border-slate-100 px-4">
        <span className="flex h-7 min-w-8 cursor-grab items-center justify-center gap-1 rounded-full bg-[var(--theme-accent-soft)] px-2 text-[11px] font-semibold text-[var(--theme-accent)]"><GripVertical size={11} />O{index}</span>
        {editingObjective ? (
          <input
            autoFocus
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            onBlur={() => {
              const value = title.trim();
              if (!value || value === objective.title) {
                cancelObjectiveEdit();
                return;
              }
              saveObjective();
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter') saveObjective();
              if (event.key === 'Escape') cancelObjectiveEdit();
            }}
            className="h-8 min-w-0 flex-1 rounded-md border border-[#cfdbea] bg-white px-3 text-[15px] font-bold leading-none text-slate-950 outline-none focus:border-[var(--theme-accent)] focus:ring-2 focus:ring-[var(--theme-accent-ring)]"
            placeholder="目标标题"
          />
        ) : (
          <button
            type="button"
            onDoubleClick={() => setEditingObjective(true)}
            className="min-w-0 flex-1 truncate text-left text-[15px] font-bold leading-5 text-slate-950"
            title="双击编辑目标"
          >
            {objective.title}
          </button>
        )}
        <button onClick={() => { if (confirm('确认删除该目标及其所有 KR？')) deleteObjective.mutate(objective.id); }} className="p-1 text-slate-300 hover:text-red-500" title="删除目标"><X size={12} /></button>
        <span className={`w-9 text-right text-[12px] font-medium tabular-nums ${progress === 100 ? 'text-emerald-600' : 'text-red-500'}`}>{progress}%</span>
        <button onClick={() => setCommentsOpen((value) => !value)} className={`flex items-center gap-1 rounded p-1 ${commentsOpen ? 'text-[var(--theme-accent)]' : 'text-slate-400 hover:text-[var(--theme-accent)]'}`} title="目标评论"><MessageSquare size={14} />{objective.comment_count > 0 && <span className="text-[10px]">{objective.comment_count}</span>}</button>
      </div>

      {commentsOpen && <OkrCommentsPanel month={month} target="objective" targetId={objective.id} />}

      {(previewKrIds ? previewKrIds.map((id) => objective.key_results.find((item) => item.id === id)).filter((item): item is KeyResultOut => Boolean(item)) : objective.key_results).map((kr, krIndex) => <KeyResultRow key={kr.id} label={`KR${krIndex + 1}`} month={month} kr={kr} draggingId={draggingKrId} isDragging={draggingKrId === kr.id} onMove={(targetId, before) => {
        const next = [...(previewKrIds ?? objective.key_results.map((item) => item.id))];
        const sourceIndex = next.indexOf(targetId);
        const [moved] = next.splice(sourceIndex, 1);
        const targetIndex = next.indexOf(kr.id);
        next.splice(targetIndex < 0 ? next.length : targetIndex + (before ? 0 : 1), 0, moved);
        setPreviewKrIds(next);
      }} onDragStart={() => { setDraggingKrId(kr.id); setPreviewKrIds(objective.key_results.map((item) => item.id)); }} onDragEnd={() => { setDraggingKrId(null); setPreviewKrIds(null); }} onDropOrder={() => { reorderKeyResults.mutate({ objectiveId: objective.id, ids: previewKrIds ?? objective.key_results.map((item) => item.id) }, { onSettled: () => { setDraggingKrId(null); setPreviewKrIds(null); } }); }} />)}

      {addingKr ? (
          <AddKeyResultForm
            submitting={addKeyResult.isPending}
            onCancel={() => setAddingKr(false)}
            onSubmit={(input) => addKeyResult.mutate({ objectiveId: objective.id, input }, { onSuccess: () => setAddingKr(false) })}
          />
      ) : (
        <button onClick={() => setAddingKr(true)} className="flex h-10 w-full items-center gap-1.5 px-4 text-[12px] font-medium text-[var(--theme-accent)] hover:bg-[var(--theme-accent-soft)]"><Plus size={12} />添加关键结果</button>
      )}
    </section>
  );
}

function KeyResultRow({ label, month, kr, draggingId, onMove, isDragging, onDragStart, onDragEnd, onDropOrder }: { label: string; month: string; kr: KeyResultOut; draggingId: number | null; onMove: (targetId: number, before: boolean) => void; isDragging: boolean; onDragStart: () => void; onDragEnd: () => void; onDropOrder: (ids: number[]) => void }) {
  const [editingKr, setEditingKr] = useState(false);
  const [editingValue, setEditingValue] = useState(false);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [krTitle, setKrTitle] = useState(kr.title);
  const [markerProgress, setMarkerProgress] = useState(pct(kr.progress));
  const [progressNote, setProgressNote] = useState('');
  const [progressDate, setProgressDate] = useState(() => (
    dayjs().format('YYYY-MM') === month
      ? dayjs().format('YYYY-MM-DD')
      : dayjs(`${month}-01`).endOf('month').format('YYYY-MM-DD')
  ));
  const updateKr = useUpdateKeyResult(month);
  const deleteKr = useDeleteKeyResult(month);
  const createProgress = useCreateKeyResultProgress(month);

  useEffect(() => {
    setMarkerProgress(pct(kr.progress));
  }, [kr.progress]);

  useEffect(() => {
    setKrTitle(kr.title);
  }, [kr.title]);

  const saveCurrent = () => {
    const note = progressNote.trim();
    if (!note || createProgress.isPending) return;
    createProgress.mutate(
      { krId: kr.id, input: { note, progress_date: progressDate } },
      { onSuccess: () => { setProgressNote(''); setEditingValue(false); } },
    );
  };

  const saveMarkerProgress = (value = markerProgress) => {
    const next = Math.max(0, Math.min(100, Math.round(value)));
    if (next === pct(kr.progress) || updateKr.isPending) return;
    updateKr.mutate({ krId: kr.id, input: { progress: next } });
  };

  const saveKrTitle = () => {
    const value = krTitle.trim();
    if (!value || updateKr.isPending) return;
    updateKr.mutate(
      { krId: kr.id, input: { title: value } },
      { onSuccess: () => setEditingKr(false) },
    );
  };

  const cancelKrEdit = () => {
    setKrTitle(kr.title);
    setEditingKr(false);
  };

  return (
    <div data-okr-kr-id={kr.id} className={`border-b border-slate-100 transition-opacity duration-150 ${isDragging ? 'opacity-0' : 'opacity-100'}`} draggable onDragStart={(event) => { event.stopPropagation(); event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/okr-kr', String(kr.id)); onDragStart(); }} onDragEnd={onDragEnd} onDragOver={(event) => {
      event.preventDefault();
      const sourceId = Number(event.dataTransfer.getData('text/okr-kr')) || draggingId;
      if (sourceId && sourceId !== kr.id) {
        const bounds = event.currentTarget.getBoundingClientRect();
        onMove(sourceId, event.clientY < bounds.top + bounds.height / 2);
      }
    }} onDrop={(event) => {
      event.preventDefault();
      event.stopPropagation();
      const sourceId = Number(event.dataTransfer.getData('text/okr-kr')) || draggingId;
      if (sourceId) {
        onDropOrder([]);
      }
    }}>
    <div className="group flex min-h-[52px] items-center gap-2.5 px-4 py-2">
      <button type="button" className="w-[58px] shrink-0 text-center text-[11px] leading-5 text-slate-400 hover:text-[var(--theme-accent)]" title="关键结果">{label}</button>
      <div className="min-w-0 flex-1 text-[12px] leading-5">
        <button type="button" onDoubleClick={() => setEditingKr(true)} className="max-w-full text-left text-[12px] font-medium leading-5 text-slate-950" title="双击编辑关键结果">{kr.title}</button>
        {!editingValue && <button onClick={() => setEditingValue(true)} className="ml-2.5 text-[11px] leading-5 text-[var(--theme-accent)] hover:opacity-80">+ 更新进展</button>}
      </div>
      <button onClick={() => deleteKr.mutate(kr.id)} className="p-1 text-slate-300 hover:text-red-500" title="删除关键结果"><X size={11} /></button>
      <div className="relative hidden h-4 w-[136px] shrink-0 items-center sm:flex" title={`${label}标记 ${markerProgress}%`}>
        <span className="h-0.5 w-full rounded-full bg-slate-300" />
        <span className="absolute h-2.5 w-2.5 -translate-x-1/2 rounded-full bg-[#e3483e] shadow-[0_1px_3px_rgba(227,72,62,.25)]" style={{ left: `${markerProgress}%` }} />
        <input
          type="range"
          min={0}
          max={100}
          step={1}
          value={markerProgress}
          onChange={(event) => setMarkerProgress(Number(event.target.value))}
          onPointerUp={(event) => saveMarkerProgress(Number(event.currentTarget.value))}
          onKeyUp={(event) => {
            if (event.key === 'ArrowLeft' || event.key === 'ArrowRight' || event.key === 'Home' || event.key === 'End') {
              saveMarkerProgress(Number(event.currentTarget.value));
            }
          }}
          onBlur={(event) => saveMarkerProgress(Number(event.currentTarget.value))}
          className="absolute inset-0 h-4 w-full cursor-pointer opacity-0"
          aria-label={`${label}进度标记`}
        />
      </div>
      <span className={`w-9 text-right text-[12px] font-medium tabular-nums ${markerProgress === 100 ? 'text-emerald-600' : 'text-red-500'}`}>{markerProgress}%</span>
      <button onClick={() => setCommentsOpen((value) => !value)} className={`flex items-center gap-1 rounded p-1 ${commentsOpen ? 'text-[var(--theme-accent)]' : 'text-slate-400 hover:text-[var(--theme-accent)]'}`} title="关键结果评论"><MessageSquare size={14} />{kr.comment_count > 0 && <span className="text-[10px]">{kr.comment_count}</span>}</button>
    </div>
    {editingKr && (
      <form
        onSubmit={(event) => {
          event.preventDefault();
          saveKrTitle();
        }}
        className="bg-white px-3 py-3"
      >
        <div className="flex items-center gap-2 rounded-xl border border-[#d7e0ec] bg-white p-3">
          <input
            autoFocus
            value={krTitle}
            onChange={(event) => setKrTitle(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Escape') cancelKrEdit();
            }}
            className="h-9 min-w-0 flex-1 rounded-lg border border-[#cfdbea] bg-white px-3 text-[12px] font-medium leading-none text-slate-950 outline-none focus:border-[var(--theme-accent)] focus:ring-2 focus:ring-[var(--theme-accent-ring)]"
            placeholder="关键结果描述"
          />
          <button type="button" onClick={cancelKrEdit} className="h-8 min-w-[54px] rounded-lg border border-[#d7e0ec] bg-white px-3 text-xs text-slate-500 hover:border-slate-300">取消</button>
          <button type="submit" disabled={!krTitle.trim() || updateKr.isPending} className="h-8 min-w-[54px] rounded-lg bg-[var(--theme-accent-soft)] px-3 text-xs font-semibold text-[var(--theme-accent)] hover:bg-[var(--theme-accent)] hover:text-white disabled:opacity-40">保存</button>
        </div>
      </form>
    )}
    {kr.progress_updates.length > 0 && (
      <div className="px-[98px] pb-2 pt-0 text-[10px] leading-4 text-slate-400">
        <div className="space-y-1">
          {kr.progress_updates.map((record) => (
            <div key={record.id} className="flex items-center gap-2">
              <span>{dayjs(record.progress_date).format('M.D')}</span>
              <span className="text-slate-400">{record.note}</span>
            </div>
          ))}
        </div>
      </div>
    )}
    {editingValue && (
      <div className="bg-slate-50/40 px-4 py-3">
        <div className="rounded-xl border border-[#d7e0ec] bg-white p-3">
          <div className="flex items-center gap-2">
            <input autoFocus value={progressNote} onChange={(event) => setProgressNote(event.target.value)} placeholder="输入进展描述..." className="h-10 min-w-0 flex-1 rounded-xl border border-[#cfdbea] px-3 text-xs text-slate-700 outline-none placeholder:text-slate-400 focus:border-[var(--theme-accent)]" />
            <input type="date" min={`${month}-01`} max={dayjs(`${month}-01`).endOf('month').format('YYYY-MM-DD')} value={progressDate} onChange={(event) => setProgressDate(event.target.value)} className="h-8 rounded-lg border border-[#d7e0ec] px-3 text-xs text-slate-500 outline-none focus:border-[var(--theme-accent)]" aria-label="进展日期" />
            <button onClick={() => { setEditingValue(false); setProgressNote(''); }} className="h-8 min-w-[54px] rounded-lg border border-[#d7e0ec] bg-white px-3 text-xs text-slate-500">取消</button>
            <button onClick={saveCurrent} disabled={!progressNote.trim() || createProgress.isPending} className="h-8 min-w-[54px] rounded-lg bg-[var(--theme-accent-soft)] px-3 text-xs font-semibold text-[var(--theme-accent)] hover:bg-[var(--theme-accent)] hover:text-white disabled:opacity-40">{createProgress.isPending ? '提交中…' : '确认'}</button>
          </div>
        </div>
      </div>
    )}
    {commentsOpen && <OkrCommentsPanel month={month} target="key-result" targetId={kr.id} />}
    </div>
  );
}

function AddKeyResultForm({ submitting, onCancel, onSubmit }: { submitting: boolean; onCancel: () => void; onSubmit: (input: KeyResultInput) => void }) {
  const [title, setTitle] = useState('');
  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const value = title.trim();
    if (!value || submitting) return;
    onSubmit({ title: value });
  };

  return (
    <form onSubmit={handleSubmit} className="border-t border-slate-100 bg-slate-50/50 px-3 py-3">
      <input autoFocus value={title} onChange={(event) => setTitle(event.target.value)} placeholder="关键结果描述..." className="h-11 w-full rounded-xl border border-[#cfdbea] bg-white px-4 text-xs text-slate-800 outline-none placeholder:text-slate-400 focus:border-[var(--theme-accent)]" />
      <div className="mt-2 flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="h-8 min-w-[58px] rounded-xl border border-[#d7e0ec] bg-white px-3 text-xs text-slate-500">取消</button>
        <button type="submit" disabled={!title.trim() || submitting} className="h-8 min-w-[58px] rounded-xl bg-[var(--theme-accent)] px-3 text-xs font-semibold text-white hover:bg-[var(--theme-accent-hover)] disabled:opacity-40">{submitting ? '添加中…' : '添加'}</button>
      </div>
    </form>
  );
}

import { useState } from 'react';
import { Plus, Trash2, Pencil, HelpCircle, Lightbulb } from 'lucide-react';
import type { ProblemSolutionOut } from '@/types/api';
import RichTextEditor, { type RichTextValue } from '@/components/editor/RichTextEditor';
import { useCreateProblem, useUpdateProblem, useDeleteProblem } from './hooks';

interface ProblemListProps {
  date: string;
  problems: ProblemSolutionOut[];
}

export default function ProblemList({ date, problems }: ProblemListProps) {
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  const createProblem = useCreateProblem(date);
  const updateProblem = useUpdateProblem(date);
  const deleteProblem = useDeleteProblem(date);

  return (
    <div className="workspace-card overflow-visible">
      <div className="flex min-h-[3.25rem] items-center justify-between border-b border-slate-100 px-5">
        <h3 className="flex items-center gap-2 text-sm font-bold text-zinc-900"><Lightbulb size={16} className="theme-icon-color" />问题与解决方案 <HelpCircle size={13} className="text-slate-300" /></h3>
        <span className="text-[11px] font-normal text-zinc-400">{problems.length} 条</span>
      </div>

      {/* Rows */}
      {problems.length > 0 && <div className="space-y-3 p-3">
        {problems.map((problem) =>
          editingId === problem.id ? (
            <ProblemForm
              key={problem.id}
              submitting={updateProblem.isPending}
              initialText={problem.problem_text}
              initialContent={problem.solution_json ?? null}
              initialHtml={problem.solution_html ?? ''}
              onCancel={() => setEditingId(null)}
              onSubmit={(problemText, rich) =>
                updateProblem.mutate(
                  {
                    id: problem.id,
                    input: {
                      problem_text: problemText,
                      solution_html: rich.html,
                      solution_json: rich.json,
                    },
                  },
                  { onSuccess: () => setEditingId(null) },
                )
              }
            />
          ) : (
            <div
              key={problem.id}
              className="group rounded-xl p-4 bg-white hover:bg-zinc-50/40 border border-zinc-100 transition-colors"
            >
              <div className="flex items-start justify-between gap-3">
                <h4 className="font-semibold text-xs text-zinc-900 leading-snug">
                  {problem.problem_text}
                </h4>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={() => setEditingId(problem.id)}
                    className="cursor-pointer rounded p-1 text-zinc-300 opacity-0 transition-all hover:text-[var(--theme-accent)] group-hover:opacity-100"
                    title="编辑"
                  >
                    <Pencil size={13} />
                  </button>
                  <button
                    onClick={() => deleteProblem.mutate(problem.id)}
                    className="text-zinc-300 hover:text-red-600 opacity-0 group-hover:opacity-100 p-1 rounded transition-all cursor-pointer"
                    title="删除"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
              {problem.solution_html && (
                <div
                  className="tiptap mt-2.5 text-[11px] text-zinc-500 bg-zinc-50/50 p-3 rounded-lg border border-zinc-100 leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: problem.solution_html }}
                />
              )}
            </div>
          ),
        )}
      </div>}

      {!adding ? <button onClick={() => setAdding(true)} className={`flex h-14 w-full items-center gap-2 px-5 text-xs font-medium text-[var(--theme-accent)] hover:bg-[var(--theme-accent-soft)] ${problems.length > 0 ? 'border-t border-slate-100' : ''}`}><Plus size={14} />记录新问题</button> : (
        <div className={problems.length > 0 ? 'border-t border-slate-100' : ''}>
          <ProblemForm
            submitting={createProblem.isPending}
            onCancel={() => setAdding(false)}
            onSubmit={(problemText, rich) =>
              createProblem.mutate(
                {
                  date,
                  problem_text: problemText,
                  solution_html: rich.html,
                  solution_json: rich.json,
                },
                { onSuccess: () => setAdding(false) },
              )
            }
          />
        </div>
      )}
    </div>
  );
}

interface ProblemFormProps {
  submitting: boolean;
  initialText?: string;
  initialContent?: Record<string, unknown> | unknown[] | null;
  initialHtml?: string;
  onCancel: () => void;
  onSubmit: (problemText: string, rich: RichTextValue) => void;
}

// The solution_html the backend returns is sanitized and safe to render, so the
// preview above uses dangerouslySetInnerHTML. This form edits the raw problem
// text + TipTap rich text; the server re-sanitizes on save.
function ProblemForm({
  submitting,
  initialText = '',
  initialContent = null,
  initialHtml = '',
  onCancel,
  onSubmit,
}: ProblemFormProps) {
  const [problemText, setProblemText] = useState(initialText);
  // Seed with the existing content so editing only the problem text (without
  // touching the editor, which would leave onChange unfired) preserves the
  // original solution instead of wiping it.
  const [rich, setRich] = useState<RichTextValue>({
    html: initialHtml,
    json: (initialContent as Record<string, unknown>) ?? {},
  });

  const handleSubmit = () => {
    const text = problemText.trim();
    if (!text || submitting) return;
    onSubmit(text, rich);
  };

  return (
    <div>
      <div className="bg-slate-50/70 px-5 py-4">
        <label className="mb-3 block text-sm font-semibold text-slate-900">
          {initialText ? '编辑问题' : '问题'}
        </label>
        <textarea
          value={problemText}
          onChange={(e) => setProblemText(e.target.value)}
          placeholder="描述遇到的问题..."
          rows={3}
          className="h-[70px] w-full resize-none rounded-xl border border-[#cfdbea] bg-white px-3 py-2.5 text-xs text-zinc-800 outline-none placeholder:text-slate-400 focus:border-[var(--theme-accent)]"
        />
      </div>
      <div className="px-5 pb-3 pt-4">
        <span className="mb-3 block text-sm font-semibold text-slate-900">思考与方案</span>
        <RichTextEditor
          initialContent={initialContent as Record<string, unknown> | null}
          onChange={setRich}
          placeholder=""
          variant="problem"
        />
        <div className="mt-7 flex justify-end gap-2">
        <button
          onClick={onCancel}
          className="h-8 min-w-[80px] rounded-md border border-[#d7e0ec] bg-white px-4 text-xs text-slate-600 hover:bg-slate-50"
        >
          取消
        </button>
        <button
          onClick={handleSubmit}
          disabled={!problemText.trim() || submitting}
          className="h-8 min-w-[78px] rounded-md bg-[var(--theme-accent)] px-4 text-xs font-medium text-white shadow-sm hover:bg-[var(--theme-accent-hover)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting ? '保存中…' : '保存'}
        </button>
        </div>
      </div>
    </div>
  );
}

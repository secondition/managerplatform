import { useState } from 'react';
import { Pencil, X, FileText } from 'lucide-react';
import type { MonthlyReportSectionOut } from '@/types/api';
import RichTextEditor, { type RichTextValue } from '@/components/editor/RichTextEditor';
import { useUpdateReportSection } from './hooks';
import MonthlyReportScoreCard from './MonthlyReportScoreCard';

function parseJson(value: string | null): Record<string, unknown> | null {
  if (!value) return null;
  try {
    return JSON.parse(value) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export default function MonthlyReport({
  month,
  sections,
  monthLabel,
  aiEnabled,
}: {
  month: string;
  sections: MonthlyReportSectionOut[];
  monthLabel: string;
  aiEnabled: boolean;
}) {
  return (
    <div className="bg-white rounded-2xl p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] space-y-4">
      <div className="flex items-center gap-2">
        <span className="p-1.5 bg-[var(--theme-accent-soft)] text-[var(--theme-icon-color)] rounded-lg">
          <FileText size={13} />
        </span>
        <h3 className="text-sm font-bold text-zinc-900">{monthLabel}月报</h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sections.map((section) => (
          <SectionCard key={section.id} month={month} section={section} />
        ))}
      </div>

      {aiEnabled && <MonthlyReportScoreCard month={month} />}
    </div>
  );
}

function SectionCard({ month, section }: { month: string; section: MonthlyReportSectionOut }) {
  const [editing, setEditing] = useState(false);
  const [rich, setRich] = useState<RichTextValue>({
    html: section.content_html ?? '',
    json: parseJson(section.content_json) ?? {},
  });

  const updateSection = useUpdateReportSection(month);

  const save = () => {
    updateSection.mutate(
      {
        sectionId: section.id,
        input: {
          content_html: rich.html,
          content_json: JSON.stringify(rich.json),
        },
      },
      { onSuccess: () => setEditing(false) },
    );
  };

  return (
    <div className="rounded-xl border border-zinc-100 bg-zinc-50/20 p-4 space-y-2.5">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-zinc-700">{section.title}</h4>
        {editing ? (
          <button
            onClick={() => {
              setEditing(false);
              setRich({
                html: section.content_html ?? '',
                json: parseJson(section.content_json) ?? {},
              });
            }}
            className="text-zinc-400 hover:text-zinc-700 p-1 rounded cursor-pointer"
            aria-label="取消"
          >
            <X size={13} />
          </button>
        ) : (
          <button
            onClick={() => setEditing(true)}
            className="text-zinc-300 hover:text-[var(--theme-accent)] p-1 rounded transition-colors cursor-pointer"
            title="编辑板块"
          >
            <Pencil size={13} />
          </button>
        )}
      </div>

      {editing ? (
        <div className="space-y-2">
          <RichTextEditor
            initialContent={parseJson(section.content_json)}
            onChange={setRich}
            placeholder="记录本板块内容…"
          />
          <div className="flex justify-end">
            <button
              onClick={save}
              disabled={updateSection.isPending}
              className="bg-[var(--theme-accent)] hover:bg-[var(--theme-accent-hover)] disabled:opacity-40 text-white px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors"
            >
              {updateSection.isPending ? '保存中…' : '保存'}
            </button>
          </div>
        </div>
      ) : section.content_html ? (
        <div
          className="tiptap text-[11px] text-zinc-600 leading-relaxed"
          dangerouslySetInnerHTML={{ __html: section.content_html }}
        />
      ) : (
        <p className="text-[11px] text-zinc-300 italic">暂无内容，点右上角编辑。</p>
      )}
    </div>
  );
}

import type { LucideIcon } from 'lucide-react';
import { BookOpen, FileText, Grid2X2, Lightbulb } from 'lucide-react';

function ReservedPage({ icon: Icon, title }: { icon: LucideIcon; title: string }) {
  return (
    <div className="workspace-page">
      <section className="workspace-card flex min-h-[360px] flex-col items-center justify-center px-6 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-slate-400">
          <Icon size={22} />
        </span>
        <h1 className="mt-4 text-base font-semibold text-slate-800">{title}</h1>
        <span className="mt-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] text-slate-500">
          功能预留，暂未开放
        </span>
      </section>
    </div>
  );
}

export function InspirationsPage() {
  return <ReservedPage icon={Lightbulb} title="灵感库" />;
}

export function DocumentsPage() {
  return <ReservedPage icon={FileText} title="文档" />;
}

export function DocumentEditorPage() {
  return <ReservedPage icon={FileText} title="文档编辑器" />;
}

export function KnowledgePage() {
  return <ReservedPage icon={BookOpen} title="知识库" />;
}

export function KnowledgeArticlePage() {
  return <ReservedPage icon={BookOpen} title="知识库文章" />;
}

export function DataTablesPage() {
  return <ReservedPage icon={Grid2X2} title="多维表格" />;
}

export function DataTableEditorPage() {
  return <ReservedPage icon={Grid2X2} title="多维表格编辑器" />;
}

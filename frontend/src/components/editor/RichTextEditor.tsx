import { useEditor, EditorContent, type Editor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import Link from '@tiptap/extension-link';
import TextStyle from '@tiptap/extension-text-style';
import Color from '@tiptap/extension-color';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import Table from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableHeader from '@tiptap/extension-table-header';
import TableCell from '@tiptap/extension-table-cell';
import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  Bold,
  Image as ImageIcon,
  Italic,
  Link2,
  List,
  ListChecks,
  ListOrdered,
  Pilcrow,
  Quote,
  Redo2,
  Table2,
  Underline as UnderlineIcon,
  Undo2,
} from 'lucide-react';
import type { ReactNode } from 'react';

export interface RichTextValue {
  html: string;
  json: Record<string, unknown>;
}

interface RichTextEditorProps {
  initialContent?: Record<string, unknown> | null;
  onChange: (value: RichTextValue) => void;
  placeholder?: string;
  variant?: 'default' | 'problem';
}

// Extension set mirrors the backend sanitizer whitelist (utils/html_sanitize):
// headings/lists/link/underline/color/table/taskList all round-trip through
// bleach. Anything outside the whitelist is stripped server-side.
const EXTENSIONS = [
  StarterKit,
  Underline,
  TextStyle,
  Color,
  Link.configure({ openOnClick: false, autolink: true }),
  TaskList,
  TaskItem.configure({ nested: true }),
  Table.configure({ resizable: false }),
  TableRow,
  TableHeader,
  TableCell,
];
export default function RichTextEditor({
  initialContent,
  onChange,
  placeholder,
  variant = 'default',
}: RichTextEditorProps) {
  const editor = useEditor({
    extensions: EXTENSIONS,
    content: initialContent ?? '',
    onUpdate: ({ editor }) => {
      onChange({ html: editor.getHTML(), json: editor.getJSON() as Record<string, unknown> });
    },
    editorProps: {
      attributes: {
        class: `tiptap text-xs text-zinc-800 leading-relaxed outline-none ${variant === 'problem' ? 'min-h-[228px]' : 'min-h-[84px]'}`,
      },
    },
  });

  if (!editor) return null;

  return (
    <div className={`overflow-hidden border transition-colors focus-within:border-[var(--theme-accent)] focus-within:shadow-[0_0_0_3px_var(--theme-accent-ring)] ${variant === 'problem' ? 'rounded-xl border-[#cfdbea]' : 'rounded-xl border-zinc-200'}`}>
      <Toolbar editor={editor} variant={variant} />
      <div className={`relative ${variant === 'problem' ? 'min-h-[240px] px-4 py-3' : 'min-h-[100px] px-3 py-2'}`}>
        <EditorContent editor={editor} />
        {editor.isEmpty && placeholder && (
          <p className="pointer-events-none absolute left-4 top-3 text-xs text-zinc-300 select-none">
            {placeholder}
          </p>
        )}
      </div>
    </div>
  );
}

const BTN_BASE =
  'px-2 py-1 rounded text-[11px] font-medium transition-colors cursor-pointer select-none';

function ToolbarButton({
  active,
  onClick,
  children,
  title,
  compact = false,
  disabled = false,
}: {
  active?: boolean;
  onClick: () => void;
  children: ReactNode;
  title: string;
  compact?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
      title={title}
      disabled={disabled}
      className={`${compact ? 'flex h-8 min-w-8 items-center justify-center rounded-md px-2 text-xs transition-colors' : BTN_BASE} ${active ? (compact ? 'bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]' : 'bg-[var(--theme-accent)] text-white') : 'text-slate-500 hover:bg-slate-100'} disabled:cursor-not-allowed disabled:text-slate-300 disabled:hover:bg-transparent`}
    >
      {children}
    </button>
  );
}

function Toolbar({ editor, variant }: { editor: Editor; variant: 'default' | 'problem' }) {
  if (variant === 'problem') return <ProblemToolbar editor={editor} />;

  return (
    <div className="flex flex-wrap items-center gap-0.5 bg-zinc-50/80 border-b border-zinc-100 px-2 py-1.5">
      <ToolbarButton title="加粗" active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()}>
        <b>B</b>
      </ToolbarButton>
      <ToolbarButton title="斜体" active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()}>
        <i>I</i>
      </ToolbarButton>
      <ToolbarButton title="下划线" active={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()}>
        <u>U</u>
      </ToolbarButton>
      <span className="w-px h-4 bg-zinc-200 mx-1" />
      <ToolbarButton title="标题" active={editor.isActive('heading', { level: 3 })} onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}>
        H3
      </ToolbarButton>
      <ToolbarButton title="无序列表" active={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()}>
        • 列表
      </ToolbarButton>
      <ToolbarButton title="任务清单" active={editor.isActive('taskList')} onClick={() => editor.chain().focus().toggleTaskList().run()}>
        ☑ 任务
      </ToolbarButton>
      <ToolbarButton title="引用" active={editor.isActive('blockquote')} onClick={() => editor.chain().focus().toggleBlockquote().run()}>
        引用
      </ToolbarButton>
      <span className="w-px h-4 bg-zinc-200 mx-1" />
      <ToolbarButton title="插入表格" onClick={() => editor.chain().focus().insertTable({ rows: 2, cols: 2, withHeaderRow: true }).run()}>
        表格
      </ToolbarButton>
      <label className="flex items-center gap-1 px-1 cursor-pointer" title="文字颜色">
        <span className="text-[11px] text-zinc-600">色</span>
        <input
          type="color"
          onInput={(e) => editor.chain().focus().setColor((e.target as HTMLInputElement).value).run()}
          className="w-4 h-4 rounded cursor-pointer border-0 bg-transparent p-0"
        />
      </label>
    </div>
  );
}

function ToolbarDivider() {
  return <span className="mx-0.5 h-5 w-px bg-slate-200" />;
}

function ProblemToolbar({ editor }: { editor: Editor }) {
  const setLink = () => {
    const previous = editor.getAttributes('link').href as string | undefined;
    const url = window.prompt('输入链接地址', previous ?? 'https://');
    if (url === null) return;
    if (!url.trim()) {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url.trim() }).run();
  };

  return (
    <div className="flex min-h-[48px] flex-wrap items-center gap-0.5 border-b border-slate-200 bg-slate-50/80 px-3 py-2">
      <ToolbarButton compact title="撤销" onClick={() => editor.chain().focus().undo().run()} disabled={!editor.can().chain().focus().undo().run()}><Undo2 size={15} /></ToolbarButton>
      <ToolbarButton compact title="重做" onClick={() => editor.chain().focus().redo().run()} disabled={!editor.can().chain().focus().redo().run()}><Redo2 size={15} /></ToolbarButton>
      <ToolbarDivider />
      <ToolbarButton compact title="正文" active={editor.isActive('paragraph')} onClick={() => editor.chain().focus().setParagraph().run()}><Pilcrow size={15} /></ToolbarButton>
      {[1, 2, 3].map((level) => (
        <ToolbarButton key={level} compact title={`${level} 级标题`} active={editor.isActive('heading', { level })} onClick={() => editor.chain().focus().toggleHeading({ level: level as 1 | 2 | 3 }).run()}>H{level}</ToolbarButton>
      ))}
      <ToolbarButton compact title="加粗" active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()}><Bold size={15} /></ToolbarButton>
      <ToolbarButton compact title="斜体" active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()}><Italic size={15} /></ToolbarButton>
      <ToolbarButton compact title="下划线" active={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()}><UnderlineIcon size={15} /></ToolbarButton>
      <label className="relative flex h-8 min-w-8 cursor-pointer items-center justify-center rounded-md text-slate-600 hover:bg-slate-100" title="文字颜色">
        <span className="border-b-2 border-slate-800 px-1 text-sm font-semibold leading-5">A</span>
        <input type="color" onInput={(event) => editor.chain().focus().setColor((event.target as HTMLInputElement).value).run()} className="absolute inset-0 cursor-pointer opacity-0" />
      </label>
      <ToolbarDivider />
      <ToolbarButton compact title="左对齐（暂不支持保存）" onClick={() => undefined} disabled><AlignLeft size={15} /></ToolbarButton>
      <ToolbarButton compact title="居中（暂不支持保存）" onClick={() => undefined} disabled><AlignCenter size={15} /></ToolbarButton>
      <ToolbarButton compact title="右对齐（暂不支持保存）" onClick={() => undefined} disabled><AlignRight size={15} /></ToolbarButton>
      <ToolbarDivider />
      <ToolbarButton compact title="无序列表" active={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()}><List size={15} /></ToolbarButton>
      <ToolbarButton compact title="有序列表" active={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()}><ListOrdered size={15} /></ToolbarButton>
      <ToolbarButton compact title="任务清单" active={editor.isActive('taskList')} onClick={() => editor.chain().focus().toggleTaskList().run()}><ListChecks size={15} /></ToolbarButton>
      <ToolbarButton compact title="引用" active={editor.isActive('blockquote')} onClick={() => editor.chain().focus().toggleBlockquote().run()}><Quote size={15} /></ToolbarButton>
      <ToolbarDivider />
      <ToolbarButton compact title="插入表格" onClick={() => editor.chain().focus().insertTable({ rows: 2, cols: 2, withHeaderRow: true }).run()}><Table2 size={15} /></ToolbarButton>
      <ToolbarDivider />
      <ToolbarButton compact title="插入链接" active={editor.isActive('link')} onClick={setLink}><Link2 size={15} /></ToolbarButton>
      <ToolbarButton compact title="图片内容暂不支持保存" onClick={() => undefined} disabled><ImageIcon size={15} /></ToolbarButton>
    </div>
  );
}

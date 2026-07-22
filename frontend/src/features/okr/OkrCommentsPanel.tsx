import { useState, type FormEvent } from 'react';
import { Check, Pencil, Send, Trash2, X } from 'lucide-react';
import Avatar from '@/components/user/Avatar';
import { dayjs } from '@/lib/date';
import type { OkrCommentTarget } from '@/api/okr';
import {
  useCreateOkrComment,
  useDeleteOkrComment,
  useOkrComments,
  useUpdateOkrComment,
} from './hooks';

export default function OkrCommentsPanel({
  month,
  target,
  targetId,
}: {
  month: string;
  target: OkrCommentTarget;
  targetId: number;
}) {
  const comments = useOkrComments(target, targetId);
  const create = useCreateOkrComment(month, target, targetId);
  const update = useUpdateOkrComment(target, targetId);
  const remove = useDeleteOkrComment(month, target, targetId);
  const [draft, setDraft] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingContent, setEditingContent] = useState('');

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const content = draft.trim();
    if (!content || create.isPending) return;
    create.mutate(content, { onSuccess: () => setDraft('') });
  };

  return (
    <div className="border-b border-slate-100 bg-slate-50/50 px-4 py-3">
      <div className="space-y-3">
        {comments.isLoading && <p className="text-[11px] text-slate-400">正在加载评论...</p>}
        {comments.isError && <p className="text-[11px] text-red-500">评论加载失败，请稍后重试。</p>}
        {comments.data?.map((comment) => (
          <div key={comment.id} className="flex items-start gap-2.5">
            <Avatar name={comment.author.name} avatarUrl={comment.author.avatar_url} size={24} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-[11px]">
                <strong className="font-medium text-slate-700">{comment.author.name}</strong>
                <span className="text-slate-400">{dayjs(comment.created_at).format('MM-DD HH:mm')}</span>
              </div>
              {editingId === comment.id ? (
                <div className="mt-1.5 flex items-center gap-2">
                  <input
                    autoFocus
                    value={editingContent}
                    onChange={(event) => setEditingContent(event.target.value)}
                    className="h-8 min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 text-xs outline-none focus:border-[var(--theme-accent)]"
                  />
                  <button
                    onClick={() => update.mutate(
                      { commentId: comment.id, content: editingContent.trim() },
                      { onSuccess: () => setEditingId(null) },
                    )}
                    disabled={!editingContent.trim() || update.isPending}
                    className="rounded p-1 text-[var(--theme-accent)] disabled:text-slate-300"
                    title="保存评论"
                  >
                    <Check size={14} />
                  </button>
                  <button onClick={() => setEditingId(null)} className="rounded p-1 text-slate-400" title="取消编辑">
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <div className="mt-1 flex items-start gap-2">
                  <p className="min-w-0 flex-1 whitespace-pre-wrap text-xs leading-5 text-slate-600">{comment.content}</p>
                  {comment.can_edit && (
                    <div className="flex shrink-0 items-center">
                      <button
                        onClick={() => { setEditingId(comment.id); setEditingContent(comment.content); }}
                        className="rounded p-1 text-slate-400 hover:text-[var(--theme-accent)]"
                        title="编辑评论"
                      >
                        <Pencil size={12} />
                      </button>
                      <button
                        onClick={() => window.confirm('删除这条评论？') && remove.mutate(comment.id)}
                        className="rounded p-1 text-slate-400 hover:text-red-500"
                        title="删除评论"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
        {comments.data?.length === 0 && <p className="text-[11px] text-slate-400">暂无评论。</p>}
      </div>

      <form onSubmit={submit} className="mt-3 flex items-center gap-2">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="输入评论..."
          className="h-9 min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 text-xs outline-none placeholder:text-slate-400 focus:border-[var(--theme-accent)]"
        />
        <button
          type="submit"
          disabled={!draft.trim() || create.isPending}
          className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--theme-accent)] text-white hover:bg-[var(--theme-accent-hover)] disabled:opacity-40"
          title="发送评论"
        >
          <Send size={13} />
        </button>
      </form>
    </div>
  );
}

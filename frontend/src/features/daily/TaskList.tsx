import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import {
  CheckSquare,
  HelpCircle,
  Lock,
  Paperclip,
  Plus,
  Send,
  Square,
  StickyNote,
  Trash2,
  Users,
} from 'lucide-react';
import UserProfileLink from '@/components/user/UserProfileLink';
import UserSelectPopover from '@/components/user/UserSelectPopover';
import { dayjs } from '@/lib/date';
import { useAuthStore } from '@/stores/authStore';
import type { DailyTaskOut, RepeatRule } from '@/types/api';
import { useOkrMonth } from '@/features/okr/hooks';
import { useDailyScore } from './aiHooks';
import { useCreateTask, useDeleteTask, useSetTaskDone, useUpdateTask } from './hooks';

const HOURS = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'));
const MINUTES = Array.from({ length: 12 }, (_, i) => String(i * 5).padStart(2, '0'));

const REPEAT_LABEL: Record<RepeatRule, string> = {
  none: '今日',
  daily: '每日',
  weekly: '每周',
};

interface TaskDraft {
  hour: string;
  minute: string;
  content: string;
  note: string;
  repeat: RepeatRule;
  collaboratorIds: number[];
  assigneeIds: number[];
  isPrivate: boolean;
}

function nowFloored(): Pick<TaskDraft, 'hour' | 'minute'> {
  const now = dayjs();
  return {
    hour: String(now.hour()).padStart(2, '0'),
    minute: String(Math.floor(now.minute() / 5) * 5).padStart(2, '0'),
  };
}

function emptyDraft(): TaskDraft {
  return {
    ...nowFloored(),
    content: '',
    note: '',
    repeat: 'none',
    collaboratorIds: [],
    assigneeIds: [],
    isPrivate: false,
  };
}

function draftFromTask(task: DailyTaskOut): TaskDraft {
  const [hour, minute] = task.task_time.slice(0, 5).split(':');
  return {
    hour,
    minute,
    content: task.content,
    note: task.note ?? '',
    repeat: task.repeat_rule,
    collaboratorIds: task.collaborators.map((collaborator) => collaborator.id),
    assigneeIds: [],
    isPrivate: task.is_private,
  };
}

interface TaskListProps {
  date: string;
  tasks: DailyTaskOut[];
  calendar?: ReactNode;
  calendarOnly?: boolean;
  calendarLabel?: string;
  addRequest?: number;
}

export default function TaskList({
  date,
  tasks,
  calendar,
  calendarOnly = false,
  calendarLabel,
  addRequest = 0,
}: TaskListProps) {
  const currentUserId = useAuthStore((state) => state.user?.id ?? 0);
  const [adding, setAdding] = useState(false);
  const [addDraft, setAddDraft] = useState<TaskDraft>(emptyDraft);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<TaskDraft>(emptyDraft);

  const createTask = useCreateTask(date);
  const setDone = useSetTaskDone(date);
  const updateTask = useUpdateTask(date);
  const deleteTask = useDeleteTask(date);
  const dailyScore = useDailyScore(date);
  const okrMonth = useOkrMonth(dayjs(date).format('YYYY-MM'));

  useEffect(() => {
    setAdding(false);
    setEditingId(null);
    setAddDraft(emptyDraft());
  }, [date]);

  useEffect(() => {
    if (addRequest <= 0) return;
    setEditingId(null);
    setAdding(true);
  }, [addRequest]);

  const completed = tasks.filter((task) => task.is_done).length;
  const orderedTasks = [...tasks].sort(
    (left, right) => left.task_time.localeCompare(right.task_time) || left.id - right.id,
  );
  const dailyScoreText = dailyScore.isLoading
    ? '今日得分加载中'
    : dailyScore.data?.status === 'ready' && dailyScore.data.total_score != null
      ? `今日得分 ${dailyScore.data.total_score}分`
      : '今日得分未生成';
  const okrScore = okrMonth.data?.review.status === 'ready'
    ? okrMonth.data.review.quality_score
    : null;

  const submitAdd = (event: FormEvent) => {
    event.preventDefault();
    const content = addDraft.content.trim();
    if (!content || createTask.isPending) return;
    createTask.mutate(
      {
        date,
        task_time: `${addDraft.hour}:${addDraft.minute}:00`,
        content,
        note: addDraft.note.trim() || null,
        repeat_rule: addDraft.repeat,
        collaborator_ids: addDraft.collaboratorIds,
        assigned_to_ids: addDraft.assigneeIds,
        is_private: addDraft.isPrivate,
      },
      {
        onSuccess: () => {
          setAddDraft(emptyDraft());
          setAdding(false);
        },
      },
    );
  };

  const beginEdit = (task: DailyTaskOut) => {
    if (!task.can_edit) return;
    setAdding(false);
    setEditDraft(draftFromTask(task));
    setEditingId(task.id);
  };

  const submitEdit = (event: FormEvent) => {
    event.preventDefault();
    if (editingId === null) return;
    const content = editDraft.content.trim();
    if (!content || updateTask.isPending) return;
    updateTask.mutate(
      {
        id: editingId,
        input: {
          task_time: `${editDraft.hour}:${editDraft.minute}:00`,
          content,
          note: editDraft.note.trim() || null,
          repeat_rule: editDraft.repeat,
          collaborator_ids: editDraft.collaboratorIds,
          assigned_to_ids: editDraft.assigneeIds,
          is_private: editDraft.isPrivate,
        },
      },
      { onSuccess: () => setEditingId(null) },
    );
  };

  return (
    <div className="workspace-card overflow-visible">
      <div className="flex min-h-[3.25rem] flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-5 py-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-zinc-900">
          <CheckSquare size={16} className="theme-icon-color" />
          工作清单
          <HelpCircle size={13} className="text-slate-300" />
        </h3>
        {calendarOnly ? (
          <span className="text-[11px] font-medium text-slate-400">{calendarLabel}</span>
        ) : (
          <div className="flex flex-wrap items-center justify-end gap-3 text-[11px]">
            <span className="rounded-full bg-amber-50 px-2 py-1 text-amber-600">{dailyScoreText}</span>
            {okrScore != null && <span className="text-emerald-600">OKR {okrScore}分</span>}
            <span className="font-mono text-zinc-400">{completed}/{tasks.length} 已完成</span>
          </div>
        )}
      </div>

      {calendar}

      {!calendarOnly && orderedTasks.length > 0 && (
        <div className="space-y-1.5 p-3">
          {orderedTasks.map((task) => (
            editingId === task.id ? (
              <TaskEditor
                key={task.id}
                draft={editDraft}
                currentUserId={currentUserId}
                submitting={updateTask.isPending}
                submitLabel="保存"
                onChange={(patch) => setEditDraft((current) => ({ ...current, ...patch }))}
                onCancel={() => setEditingId(null)}
                onSubmit={submitEdit}
              />
            ) : (
              <TaskRow
                key={task.id}
                task={task}
                onToggleDone={() => setDone.mutate({ id: task.id, isDone: !task.is_done })}
                onEdit={() => beginEdit(task)}
                onDelete={() => deleteTask.mutate(task.id)}
              />
            )
          ))}
        </div>
      )}

      {!calendarOnly && (!adding ? (
        <button
          type="button"
          onClick={() => {
            setEditingId(null);
            setAdding(true);
          }}
          className={`flex h-14 w-full items-center gap-2 px-5 text-xs font-medium text-[var(--theme-accent)] hover:bg-[var(--theme-accent-soft)] ${orderedTasks.length > 0 ? 'border-t border-slate-100' : ''}`}
        >
          <Plus size={15} />
          添加事项
        </button>
      ) : (
        <div className={orderedTasks.length > 0 ? 'border-t border-slate-100 p-3' : 'p-3'}>
          <TaskEditor
            draft={addDraft}
            currentUserId={currentUserId}
            submitting={createTask.isPending}
            submitLabel={createTask.isPending ? '添加中…' : '添加'}
            onChange={(patch) => setAddDraft((current) => ({ ...current, ...patch }))}
            onCancel={() => {
              setAddDraft(emptyDraft());
              setAdding(false);
            }}
            onSubmit={submitAdd}
          />
        </div>
      ))}
    </div>
  );
}

function TaskRow({
  task,
  onToggleDone,
  onEdit,
  onDelete,
}: {
  task: DailyTaskOut;
  onToggleDone: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const dispatchedToMe = task.source === 'assigned' && task.permission === 'owner';
  const isCollaborator = task.permission === 'collaborator';
  const hasMetadata = dispatchedToMe || isCollaborator || task.is_private || task.collaborators.length > 0;

  return (
    <div
      data-daily-task-id={task.id}
      onDoubleClick={task.can_edit ? onEdit : undefined}
      title={task.can_edit ? '双击编辑事项' : undefined}
      className={`group flex min-h-[3.375rem] items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-zinc-50/70 ${task.can_edit ? 'cursor-default' : ''}`}
    >
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          if (task.can_toggle_done) onToggleDone();
        }}
        onDoubleClick={(event) => event.stopPropagation()}
        disabled={!task.can_toggle_done}
        className={`shrink-0 transition-colors ${
          task.can_toggle_done
            ? 'cursor-pointer text-zinc-400 hover:text-[var(--theme-accent)]'
            : 'cursor-not-allowed text-zinc-300'
        }`}
        title={task.can_toggle_done ? (task.is_done ? '标记未完成' : '标记完成') : '仅查看'}
      >
        {task.is_done ? <CheckSquare size={16} className="text-[var(--theme-accent)]" /> : <Square size={16} />}
      </button>
      <span className="w-11 shrink-0 font-mono text-[11px] text-zinc-400">
        {task.task_time.slice(0, 5)}
      </span>
      <div className="min-w-0 flex-1">
        <span className={`text-xs ${task.is_done ? 'text-zinc-400 line-through' : 'text-zinc-800'}`}>
          {task.content}
        </span>
        {task.note && (
          <p className="mt-0.5 flex items-start gap-1 text-[10px] text-amber-700">
            <StickyNote size={10} className="mt-0.5 shrink-0" />
            <span>{task.note}</span>
          </p>
        )}
        {hasMetadata && (
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            {task.is_private && (
              <span className="inline-flex items-center gap-0.5 rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-600">
                <Lock size={9} />
                私人
              </span>
            )}
            {dispatchedToMe && (
              <span className="inline-flex items-center gap-0.5 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-700">
                <Send size={9} />
                派发任务
              </span>
            )}
            {isCollaborator && (
              <span className="inline-flex items-center gap-0.5 rounded bg-blue-50 px-1.5 py-0.5 text-[10px] text-blue-700">
                协作任务
              </span>
            )}
            {task.collaborators.length > 0 && (
              <span className="flex items-center -space-x-1.5">
                {task.collaborators.map((collaborator) => (
                  <UserProfileLink
                    key={collaborator.id}
                    user={collaborator}
                    size={18}
                    showName={false}
                    avatarClassName="ring-1 ring-white"
                    className="hover:z-10"
                  />
                ))}
              </span>
            )}
          </div>
        )}
      </div>
      {task.can_delete && (
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onDelete();
          }}
          onDoubleClick={(event) => event.stopPropagation()}
          className="shrink-0 rounded p-1 text-zinc-300 opacity-0 transition-all hover:bg-red-50 hover:text-red-600 group-hover:opacity-100"
          title="删除事项"
        >
          <Trash2 size={13} />
        </button>
      )}
      <span className="inline-flex w-12 shrink-0 justify-center rounded-full bg-zinc-100 px-2 py-1 text-[10px] leading-4 text-zinc-500">
        {REPEAT_LABEL[task.repeat_rule]}
      </span>
    </div>
  );
}

function TaskEditor({
  draft,
  currentUserId,
  submitting,
  submitLabel,
  onChange,
  onCancel,
  onSubmit,
}: {
  draft: TaskDraft;
  currentUserId: number;
  submitting: boolean;
  submitLabel: string;
  onChange: (patch: Partial<TaskDraft>) => void;
  onCancel: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <form onSubmit={onSubmit} className="rounded-lg border border-[var(--theme-accent-ring)] bg-[var(--theme-accent-soft)] p-3">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={draft.hour}
          onChange={(event) => onChange({ hour: event.target.value })}
          className={TIME_SELECT_CLASS}
          aria-label="小时"
        >
          {HOURS.map((hour) => <option key={hour} value={hour}>{hour}</option>)}
        </select>
        <select
          value={draft.minute}
          onChange={(event) => onChange({ minute: event.target.value })}
          className={TIME_SELECT_CLASS}
          aria-label="分钟"
        >
          {MINUTES.map((minute) => <option key={minute} value={minute}>{minute}</option>)}
        </select>
        <input
          autoFocus
          value={draft.content}
          onChange={(event) => onChange({ content: event.target.value })}
          placeholder="事项内容"
          className="h-10 min-w-[260px] flex-1 rounded-lg border border-slate-800 bg-white px-4 text-xs text-zinc-800 outline-none placeholder:text-slate-400 focus:border-[var(--theme-accent)]"
        />
      </div>

      <input
        value={draft.note}
        onChange={(event) => onChange({ note: event.target.value })}
        placeholder="可选标注：虽不在 OKR 但重要，原因是…"
        className="mt-2 h-9 w-full rounded-lg border border-[#d7e0ec] bg-white px-3 text-[11px] text-zinc-700 outline-none placeholder:text-zinc-400 focus:border-[var(--theme-accent)]"
      />

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <div className="inline-flex h-8 overflow-hidden rounded-md border border-[#d7e0ec] bg-white">
          {(['none', 'daily', 'weekly'] as RepeatRule[]).map((rule) => (
            <button
              key={rule}
              type="button"
              onClick={() => onChange({ repeat: rule })}
              className={`min-w-12 border-r border-[#d7e0ec] px-3 text-xs last:border-r-0 ${
                draft.repeat === rule
                  ? 'bg-[var(--theme-accent-soft)] font-medium text-[var(--theme-accent)]'
                  : 'text-slate-500 hover:bg-slate-50'
              }`}
            >
              {REPEAT_LABEL[rule]}
            </button>
          ))}
        </div>
        <UserSelectPopover
          label="添加协作人"
          icon={<Users size={14} />}
          multiple
          includeGroups
          selectedIds={draft.collaboratorIds}
          excludeIds={[currentUserId, ...draft.assigneeIds]}
          onChange={(collaboratorIds) => onChange({ collaboratorIds })}
          triggerClassName={PICKER_CLASS}
        />
        <UserSelectPopover
          label="派发给..."
          icon={<Send size={14} />}
          multiple
          includeGroups
          selectedIds={draft.assigneeIds}
          excludeIds={draft.collaboratorIds}
          onChange={(assigneeIds) => onChange({ assigneeIds })}
          triggerClassName={PICKER_CLASS}
        />
        <button
          type="button"
          aria-pressed={draft.isPrivate}
          onClick={() => onChange({ isPrivate: !draft.isPrivate })}
          className={`flex h-8 items-center gap-1.5 rounded-md border px-3 text-xs ${
            draft.isPrivate
              ? 'border-[var(--theme-accent)] bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]'
              : 'border-[#d7e0ec] bg-white text-slate-500 hover:border-[var(--theme-accent)]'
          }`}
        >
          <Lock size={14} />
          私人
        </button>
        <button
          type="button"
          disabled
          title="暂未开放"
          className="flex h-8 cursor-not-allowed items-center gap-1.5 rounded-md border border-slate-200 bg-slate-100 px-3 text-xs text-slate-400"
        >
          <Paperclip size={14} />
          关联文档
        </button>
      </div>

      <div className="mt-3 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="h-8 min-w-[80px] rounded-md border border-[#d7e0ec] bg-white px-4 text-xs text-slate-600 hover:bg-slate-50"
        >
          取消
        </button>
        <button
          type="submit"
          disabled={!draft.content.trim() || submitting}
          className="h-8 min-w-[78px] rounded-md bg-[var(--theme-accent)] px-4 text-xs font-medium text-white shadow-sm hover:bg-[var(--theme-accent-hover)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitLabel}
        </button>
      </div>
    </form>
  );
}

const TIME_SELECT_CLASS =
  'h-10 w-[62px] shrink-0 cursor-pointer rounded-lg border border-[#d7e0ec] bg-white px-3 font-mono text-xs text-slate-700 outline-none focus:border-[var(--theme-accent)]';

const PICKER_CLASS =
  '!h-8 !rounded-md !border !border-[#d7e0ec] !px-3 hover:!border-[var(--theme-accent)]';

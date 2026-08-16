import { useRef, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Check, Search, Users, X } from 'lucide-react';
import { listUsers, listUserGroups } from '@/api/users';
import AnchoredPopover from '@/components/ui/AnchoredPopover';
import type { UserBrief } from '@/types/api';
import Avatar from './Avatar';

interface UserSelectPopoverProps {
  selectedIds: number[];
  onChange: (ids: number[], users?: UserBrief[]) => void;
  selectedUsers?: UserBrief[];
  multiple?: boolean;
  // Users to exclude from the list (e.g. current user for a dispatch picker).
  excludeIds?: number[];
  label: string;
  icon?: ReactNode;
  triggerClassName?: string;
  // When true, list 人员组 above colleagues; picking a group expands to its
  // member_ids (minus excludeIds) and merges them into the selection.
  includeGroups?: boolean;
}

// Search + single/multi-select colleague picker. Shared by task collaborators,
// dispatch target, and traffic-metric editor/viewer members. With includeGroups,
// a 人员组 can be picked and expands to its members.
export default function UserSelectPopover({
  selectedIds,
  onChange,
  selectedUsers = [],
  multiple = true,
  excludeIds = [],
  label,
  icon,
  triggerClassName = '',
  includeGroups = false,
}: UserSelectPopoverProps) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const triggerRef = useRef<HTMLButtonElement>(null);

  const { data: users } = useQuery({
    queryKey: ['users', q],
    queryFn: () => listUsers(q),
    enabled: open,
  });

  const { data: groups } = useQuery({
    queryKey: ['user-groups'],
    queryFn: listUserGroups,
    enabled: open && includeGroups,
  });

  const excluded = new Set(excludeIds);
  const visible = (users ?? []).filter((u) => !excluded.has(u.id));
  // Only offer groups that have at least one selectable (non-excluded) member.
  const visibleGroups = includeGroups
    ? (groups ?? [])
        .map((g) => ({ ...g, member_ids: g.member_ids.filter((id) => !excluded.has(id)) }))
        .filter((g) => g.member_ids.length > 0)
    : [];

  const resolveUsers = (ids: number[]): UserBrief[] => {
    const knownUsers = new Map<number, UserBrief>();
    selectedUsers.forEach((user) => knownUsers.set(user.id, user));
    (users ?? []).forEach((user) => knownUsers.set(user.id, user));
    return ids.flatMap((id) => {
      const user = knownUsers.get(id);
      return user ? [user] : [];
    });
  };

  const toggle = (user: UserBrief) => {
    if (multiple) {
      const set = new Set(selectedIds);
      if (set.has(user.id)) set.delete(user.id);
      else set.add(user.id);
      const ids = [...set];
      onChange(ids, resolveUsers(ids));
    } else {
      const ids = selectedIds.includes(user.id) ? [] : [user.id];
      onChange(ids, resolveUsers(ids));
      setOpen(false);
    }
  };

  // Picking a group merges its members into the current selection (multi only).
  // In single-select mode a group makes no sense to collapse to one id, so we
  // still add all members and keep the popover open.
  const pickGroup = (memberIds: number[]) => {
    const set = new Set(selectedIds);
    memberIds.forEach((id) => set.add(id));
    const ids = [...set];
    onChange(ids, resolveUsers(ids));
  };

  return (
    <div className="relative inline-block">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs cursor-pointer transition-colors ${
          selectedIds.length
            ? 'bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]'
            : 'bg-zinc-50/80 text-zinc-500 hover:bg-zinc-100'
        } ${triggerClassName}`}
      >
        {icon}
        {label}
        {selectedIds.length > 0 && (
          <span className="font-mono text-[10px]">{selectedIds.length}</span>
        )}
      </button>

      <AnchoredPopover
        anchor={open ? triggerRef.current : null}
        width={240}
        offset={4}
        zIndex={1100}
        onClose={() => setOpen(false)}
      >
        <div role="listbox" className="rounded-xl border border-zinc-100 bg-white p-2">
          <div className="flex items-center gap-1.5 bg-zinc-50 rounded-lg px-2 py-1.5 mb-1.5">
            <Search size={13} className="text-zinc-400" />
            <input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="搜索姓名…"
              className="flex-1 bg-transparent text-xs outline-none"
            />
            {q && (
              <button onClick={() => setQ('')} className="text-zinc-400 hover:text-zinc-600 cursor-pointer">
                <X size={12} />
              </button>
            )}
          </div>
          <div className="max-h-56 overflow-y-auto space-y-0.5">
            {/* 人员组：选中即把成员并入选择 */}
            {visibleGroups.length > 0 && !q && (
              <>
                <p className="px-2 pt-1 pb-0.5 text-[10px] uppercase tracking-wider text-zinc-300">人员组</p>
                {visibleGroups.map((g) => {
                  const allIn = g.member_ids.every((id) => selectedIds.includes(id));
                  return (
                    <button
                      key={`g-${g.id}`}
                      type="button"
                      onClick={() => pickGroup(g.member_ids)}
                      className="w-full flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-zinc-50 cursor-pointer text-left"
                    >
                      <span className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]">
                        <Users size={12} />
                      </span>
                      <span className="flex-1 text-xs text-zinc-700 truncate">
                        {g.name}
                        <span className="ml-1 text-[10px] text-zinc-400">{g.member_ids.length} 人</span>
                      </span>
                      {allIn && <Check size={14} className="shrink-0 text-[var(--theme-accent)]" />}
                    </button>
                  );
                })}
                <p className="px-2 pt-1 pb-0.5 text-[10px] uppercase tracking-wider text-zinc-300">同事</p>
              </>
            )}
            {visible.length === 0 && (
              <p className="text-[11px] text-zinc-400 text-center py-4">没有匹配的同事</p>
            )}
            {visible.map((user) => {
              const selected = selectedIds.includes(user.id);
              return (
                <button
                  key={user.id}
                  type="button"
                  onClick={() => toggle(user)}
                  className="w-full flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-zinc-50 cursor-pointer text-left"
                >
                  <Avatar name={user.name} avatarUrl={user.avatar_url} size={22} />
                  <span className="flex-1 text-xs text-zinc-700 truncate">{user.name}</span>
                  {selected && <Check size={14} className="shrink-0 text-[var(--theme-accent)]" />}
                </button>
              );
            })}
          </div>
        </div>
      </AnchoredPopover>
    </div>
  );
}

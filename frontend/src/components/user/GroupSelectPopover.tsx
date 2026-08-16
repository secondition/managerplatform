import { useQuery } from '@tanstack/react-query';
import { Check, Search, UsersRound, X } from 'lucide-react';
import { useRef, useState, type ReactNode } from 'react';
import { listUserGroups } from '@/api/users';
import AnchoredPopover from '@/components/ui/AnchoredPopover';

export interface GroupSelectItem {
  id: number;
  name: string;
  memberCount: number;
}

interface GroupSelectPopoverProps {
  selectedIds: number[];
  selectedGroups?: GroupSelectItem[];
  onChange: (ids: number[], groups: GroupSelectItem[]) => void;
  label: string;
  icon?: ReactNode;
  triggerClassName?: string;
}

export default function GroupSelectPopover({
  selectedIds,
  selectedGroups = [],
  onChange,
  label,
  icon,
  triggerClassName = '',
}: GroupSelectPopoverProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const triggerRef = useRef<HTMLButtonElement>(null);
  const groupsQuery = useQuery({
    queryKey: ['user-groups'],
    queryFn: listUserGroups,
    enabled: open,
  });

  const availableGroups = groupsQuery.data ?? [];
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const visibleGroups = availableGroups.filter((group) => (
    !normalizedQuery || group.name.toLocaleLowerCase().includes(normalizedQuery)
  ));
  const knownGroups = new Map<number, GroupSelectItem>();
  selectedGroups.forEach((group) => knownGroups.set(group.id, group));
  availableGroups.forEach((group) => knownGroups.set(group.id, {
    id: group.id,
    name: group.name,
    memberCount: group.member_ids.length,
  }));

  function toggle(groupId: number) {
    const nextIds = selectedIds.includes(groupId)
      ? selectedIds.filter((id) => id !== groupId)
      : [...selectedIds, groupId];
    onChange(
      nextIds,
      nextIds.flatMap((id) => {
        const group = knownGroups.get(id);
        return group ? [group] : [];
      }),
    );
  }

  return (
    <div className="relative inline-block">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`flex cursor-pointer items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs transition-colors ${
          selectedIds.length
            ? 'bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]'
            : 'bg-zinc-50/80 text-zinc-500 hover:bg-zinc-100'
        } ${triggerClassName}`}
      >
        {icon}
        {label}
        {selectedIds.length > 0 ? (
          <span className="font-mono text-[10px]">{selectedIds.length}</span>
        ) : null}
      </button>

      <AnchoredPopover
        anchor={open ? triggerRef.current : null}
        width={260}
        offset={4}
        zIndex={1100}
        onClose={() => setOpen(false)}
      >
        <div role="listbox" aria-multiselectable className="rounded-xl border border-zinc-100 bg-white p-2">
          <div className="mb-1.5 flex items-center gap-1.5 rounded-lg bg-zinc-50 px-2 py-1.5">
            <Search size={13} className="text-zinc-400" />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索人员组…"
              className="flex-1 bg-transparent text-xs outline-none"
            />
            {query ? (
              <button
                type="button"
                onClick={() => setQuery('')}
                className="cursor-pointer text-zinc-400 hover:text-zinc-600"
                aria-label="清空搜索"
              >
                <X size={12} />
              </button>
            ) : null}
          </div>
          <div className="max-h-56 space-y-0.5 overflow-y-auto">
            {groupsQuery.isPending ? (
              <p className="py-4 text-center text-[11px] text-zinc-400">正在加载人员组…</p>
            ) : null}
            {groupsQuery.isError ? (
              <p className="py-4 text-center text-[11px] text-rose-500">人员组加载失败</p>
            ) : null}
            {groupsQuery.isSuccess && visibleGroups.length === 0 ? (
              <p className="py-4 text-center text-[11px] text-zinc-400">没有匹配的人员组</p>
            ) : null}
            {visibleGroups.map((group) => {
              const selected = selectedIds.includes(group.id);
              return (
                <button
                  key={group.id}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onClick={() => toggle(group.id)}
                  className="flex w-full cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-zinc-50"
                >
                  <span className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]">
                    <UsersRound size={12} />
                  </span>
                  <span className="min-w-0 flex-1 truncate text-xs text-zinc-700">
                    {group.name}
                    <span className="ml-1 text-[10px] text-zinc-400">{group.member_ids.length} 人</span>
                  </span>
                  {selected ? <Check size={14} className="shrink-0 text-[var(--theme-accent)]" /> : null}
                </button>
              );
            })}
          </div>
        </div>
      </AnchoredPopover>
    </div>
  );
}

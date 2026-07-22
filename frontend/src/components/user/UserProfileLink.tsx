import { Link } from 'react-router-dom';
import type { MouseEvent } from 'react';
import type { UserBrief } from '@/types/api';
import Avatar from './Avatar';

interface UserProfileLinkProps {
  user: UserBrief;
  size?: number;
  className?: string;
  avatarClassName?: string;
  showName?: boolean;
  nameClassName?: string;
  onClick?: (event: MouseEvent<HTMLAnchorElement>) => void;
}

export default function UserProfileLink({
  user,
  size = 24,
  className = '',
  avatarClassName = '',
  showName = true,
  nameClassName = 'text-xs font-medium truncate',
  onClick,
}: UserProfileLinkProps) {
  return (
    <Link
      to={`/people/${user.id}`}
      onClick={onClick}
      title={`查看 ${user.name} 的主页`}
      className={`inline-flex items-center gap-2 min-w-0 hover:text-[var(--theme-accent)] ${className}`}
    >
      <Avatar name={user.name} avatarUrl={user.avatar_url} size={size} className={avatarClassName} />
      {showName && <span className={nameClassName}>{user.name}</span>}
    </Link>
  );
}

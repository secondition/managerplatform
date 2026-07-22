interface AvatarProps {
  name: string;
  // Kept for call-site compatibility but intentionally ignored: avatars always
  // render the name initials, custom images are no longer shown.
  avatarUrl?: string | null;
  size?: number;
  className?: string;
}

// Colored initials chip (first 1-2 chars of the name). Custom/uploaded avatar
// images are no longer displayed — every avatar is the name initials.
export default function Avatar({ name, size = 24, className = '' }: AvatarProps) {
  const dimension = { width: size, height: size, fontSize: Math.max(9, size * 0.4) };
  return (
    <span
      style={dimension}
      className={`rounded-full bg-[var(--theme-accent-soft)] text-[var(--theme-accent)] flex items-center justify-center font-semibold shrink-0 ${className}`}
      title={name}
    >
      {name.slice(0, 2)}
    </span>
  );
}

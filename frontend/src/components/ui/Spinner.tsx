import { Loader2 } from 'lucide-react';

export default function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-xs text-zinc-400">
      <Loader2 size={15} className="animate-spin" />
      {label && <span>{label}</span>}
    </div>
  );
}

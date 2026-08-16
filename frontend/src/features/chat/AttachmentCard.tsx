import {
  CircleAlert,
  Download,
  ExternalLink,
  FileSpreadsheet,
  LoaderCircle,
} from 'lucide-react';
import type { AssistantFileMessage } from './types';

interface AttachmentCardProps {
  message: AssistantFileMessage;
  onAction?: (message: AssistantFileMessage) => void;
}

const STATUS_COPY = {
  available: {
    label: '已可下载',
    description: '文件将通过平台鉴权接口下载',
    tone: 'text-emerald-600',
    action: '下载文件',
    icon: Download,
  },
  preparing: {
    label: '正在准备',
    description: '文件仍在同步，请稍后再试',
    tone: 'text-blue-600',
    action: null,
    icon: LoaderCircle,
  },
  too_large: {
    label: '文件过大',
    description: '超过网页代理下载大小限制',
    tone: 'text-amber-600',
    action: '前往飞书查看',
    icon: ExternalLink,
  },
  unavailable: {
    label: '暂不可用',
    description: '文件已失效或当前应用没有读取权限',
    tone: 'text-rose-600',
    action: null,
    icon: CircleAlert,
  },
  view_in_feishu: {
    label: '仅支持飞书查看',
    description: '飞书不允许当前应用代理下载此文件',
    tone: 'text-blue-600',
    action: '前往飞书查看',
    icon: ExternalLink,
  },
} as const;

export default function AttachmentCard({ message, onAction }: AttachmentCardProps) {
  const status = STATUS_COPY[message.download_status];
  const StatusIcon = status.icon;
  const safeDownloadUrl = getSafeDownloadUrl(message.download_url);

  return (
    <div className="w-full min-w-0 rounded-xl border border-slate-200 bg-white p-3 shadow-[0_2px_8px_rgba(15,23,42,0.03)] sm:min-w-72">
      <div className="flex min-w-0 items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
          <FileSpreadsheet size={19} />
        </span>
        <div className="min-w-0 flex-1">
          <strong className="block truncate text-[12px] font-semibold text-slate-800" title={message.file_name}>
            {message.file_name}
          </strong>
          <span className="mt-0.5 block text-[9px] text-slate-400">
            {[formatFileType(message.file_type), formatFileSize(message.file_size)].filter(Boolean).join(' · ') || '文件'}
          </span>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2.5">
        <span className={`inline-flex min-w-0 items-center gap-1.5 text-[9px] ${status.tone}`}>
          <StatusIcon size={11} className={message.download_status === 'preparing' ? 'animate-spin' : undefined} />
          <span>
            <strong className="font-semibold">{status.label}</strong>
            <span className="ml-1 text-slate-400">{status.description}</span>
          </span>
        </span>
        {status.action ? (
          message.download_status === 'available' && safeDownloadUrl ? (
            <a
              href={safeDownloadUrl}
              className="inline-flex h-7 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 text-[9px] font-medium text-slate-600 hover:border-[var(--theme-accent)] hover:text-[var(--theme-accent)]"
            >
              <StatusIcon size={11} /> {status.action}
            </a>
          ) : (
            <button
              type="button"
              onClick={() => onAction?.(message)}
              className="inline-flex h-7 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 text-[9px] font-medium text-slate-600 hover:border-[var(--theme-accent)] hover:text-[var(--theme-accent)]"
            >
              <StatusIcon size={11} /> {status.action}
            </button>
          )
        ) : null}
      </div>
    </div>
  );
}

function formatFileType(fileType: string | null) {
  if (!fileType) return null;
  return fileType.replace(/^application\//, '').replace('vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'XLSX').toUpperCase();
}

function formatFileSize(fileSize: number | null) {
  if (fileSize === null || fileSize < 0) return null;
  if (fileSize < 1024) return `${fileSize} B`;
  if (fileSize < 1024 * 1024) return `${(fileSize / 1024).toFixed(1)} KB`;
  return `${(fileSize / (1024 * 1024)).toFixed(1)} MB`;
}

function getSafeDownloadUrl(value: string | null) {
  if (!value || typeof window === 'undefined') return null;

  try {
    const url = new URL(value, window.location.origin);
    if (url.origin !== window.location.origin || !url.pathname.startsWith('/api/')) return null;
    return `${url.pathname}${url.search}`;
  } catch {
    return null;
  }
}

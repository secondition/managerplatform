import MarkdownIt from 'markdown-it';
import { createElement, Fragment, useMemo, type ElementType, type ReactNode } from 'react';

const markdown = new MarkdownIt('default', {
  html: false,
  linkify: false,
  typographer: false,
  breaks: true,
});

type MarkdownToken = ReturnType<typeof markdown.parse>[number];

const TAG_CLASSES: Record<string, string> = {
  p: 'my-2 first:mt-0 last:mb-0',
  h1: 'mb-2 mt-4 text-base font-semibold first:mt-0',
  h2: 'mb-2 mt-4 text-[15px] font-semibold first:mt-0',
  h3: 'mb-1.5 mt-3 text-sm font-semibold first:mt-0',
  h4: 'mb-1.5 mt-3 text-[13px] font-semibold first:mt-0',
  h5: 'mb-1 mt-2 text-xs font-semibold first:mt-0',
  h6: 'mb-1 mt-2 text-xs font-medium text-slate-600 first:mt-0',
  ul: 'my-2 list-disc space-y-1 pl-5',
  ol: 'my-2 list-decimal space-y-1 pl-5',
  li: 'pl-0.5',
  blockquote: 'my-2 border-l-2 border-slate-300 pl-3 text-slate-500',
  strong: 'font-semibold text-slate-800',
  em: 'italic',
  s: 'line-through opacity-75',
  thead: 'bg-slate-100 text-slate-700',
  th: 'whitespace-nowrap border border-slate-200 px-2.5 py-1.5 text-left font-semibold',
  td: 'border border-slate-200 px-2.5 py-1.5 align-top',
  tr: 'even:bg-white/70',
};

const ALLOWED_TAGS = new Set(Object.keys(TAG_CLASSES));

interface MarkdownMessageProps {
  source: string;
}

export default function MarkdownMessage({ source }: MarkdownMessageProps) {
  const content = useMemo(() => renderMarkdown(source), [source]);
  return <div className="min-w-0 break-words text-[12px] leading-5">{content}</div>;
}

function renderMarkdown(source: string) {
  const tokens = markdown.parse(source, {});
  return renderTokenSequence(tokens, 'block').nodes;
}

function renderTokenSequence(
  tokens: MarkdownToken[],
  keyPrefix: string,
  startIndex = 0,
): { nodes: ReactNode[]; nextIndex: number } {
  const nodes: ReactNode[] = [];
  let index = startIndex;

  while (index < tokens.length) {
    const token = tokens[index];
    const key = `${keyPrefix}-${index}`;

    if (token.nesting === -1) {
      return { nodes, nextIndex: index + 1 };
    }

    if (token.nesting === 1) {
      const nested = renderTokenSequence(tokens, key, index + 1);
      nodes.push(renderContainerToken(token, nested.nodes, key));
      index = nested.nextIndex;
      continue;
    }

    nodes.push(...renderStandaloneToken(token, key));
    index += 1;
  }

  return { nodes, nextIndex: index };
}

function renderContainerToken(token: MarkdownToken, children: ReactNode[], key: string): ReactNode {
  if (token.type === 'link_open') {
    const href = token.attrGet('href');
    if (!href || !isSafeLink(href)) {
      return createElement(Fragment, { key }, children);
    }
    return createElement(
      'a',
      {
        key,
        href,
        target: '_blank',
        rel: 'noopener noreferrer nofollow',
        className: 'font-medium text-[var(--theme-accent)] underline decoration-current/30 underline-offset-2 hover:decoration-current',
      },
      children,
    );
  }

  if (token.tag === 'table') {
    return createElement(
      'div',
      { key, className: 'my-3 max-w-full overflow-x-auto rounded-lg border border-slate-200' },
      createElement('table', { className: 'min-w-full border-collapse text-[11px]' }, children),
    );
  }

  if (!ALLOWED_TAGS.has(token.tag)) {
    return createElement(Fragment, { key }, children);
  }

  return createElement(
    token.tag as ElementType,
    { key, className: TAG_CLASSES[token.tag] },
    children,
  );
}

function renderStandaloneToken(token: MarkdownToken, key: string): ReactNode[] {
  if (token.type === 'inline') {
    return token.children ? renderTokenSequence(token.children, key).nodes : [];
  }

  if (token.type === 'text') return [token.content];
  if (token.type === 'softbreak' || token.type === 'hardbreak') {
    return [createElement('br', { key })];
  }
  if (token.type === 'code_inline') {
    return [
      createElement(
        'code',
        { key, className: 'rounded bg-slate-200/70 px-1 py-0.5 font-mono text-[11px] text-slate-800' },
        token.content,
      ),
    ];
  }
  if (token.type === 'fence' || token.type === 'code_block') {
    const language = token.info.trim().split(/\s+/, 1)[0];
    return [
      createElement(
        'div',
        { key, className: 'my-3 max-w-full overflow-hidden rounded-lg bg-slate-900 text-slate-100' },
        language
          ? createElement('div', { className: 'border-b border-white/10 px-3 py-1 text-[9px] text-slate-400' }, language)
          : null,
        createElement(
          'pre',
          { className: 'max-w-full overflow-x-auto p-3 font-mono text-[11px] leading-5' },
          createElement('code', null, token.content),
        ),
      ),
    ];
  }
  if (token.type === 'hr') {
    return [createElement('hr', { key, className: 'my-3 border-slate-200' })];
  }
  if (token.type === 'image') {
    return [
      createElement(
        'span',
        {
          key,
          className: 'my-2 inline-flex rounded-md border border-slate-200 bg-slate-100 px-2 py-1 text-[10px] text-slate-500',
          title: '为保护隐私与网络安全，聊天消息中的远程图片不会自动加载',
        },
        `图片已隐藏${token.content ? `：${token.content}` : ''}`,
      ),
    ];
  }
  if (token.type === 'html_inline' || token.type === 'html_block') {
    return [token.content];
  }

  return token.content ? [token.content] : [];
}

function isSafeLink(value: string) {
  const normalized = value.trim().replace(/[\u0000-\u001F\u007F\s]+/g, '').toLowerCase();
  return normalized.startsWith('https://')
    || normalized.startsWith('http://')
    || normalized.startsWith('mailto:');
}

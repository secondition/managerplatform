import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

interface AnchoredPopoverProps {
  anchor: HTMLElement | null;
  width?: number;
  offset?: number;
  zIndex?: number;
  borderRadius?: number;
  align?: 'start' | 'end';
  closeOnScroll?: boolean;
  onClose: () => void;
  children: ReactNode;
}

const VIEWPORT_MARGIN = 12;

export default function AnchoredPopover({
  anchor,
  width = 300,
  offset = 8,
  zIndex = 1000,
  borderRadius = 12,
  align = 'start',
  closeOnScroll = false,
  onClose,
  children,
}: AnchoredPopoverProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ left: VIEWPORT_MARGIN, top: VIEWPORT_MARGIN });
  const [panelWidth, setPanelWidth] = useState(width);
  const [maxHeight, setMaxHeight] = useState(window.innerHeight - VIEWPORT_MARGIN * 2);

  useLayoutEffect(() => {
    if (!anchor) return;

    const updatePosition = () => {
      const rect = anchor.getBoundingClientRect();
      const nextWidth = Math.min(width, window.innerWidth - VIEWPORT_MARGIN * 2);
      const preferredLeft = align === 'end' ? rect.right - nextWidth : rect.left;
      const maxLeft = Math.max(VIEWPORT_MARGIN, window.innerWidth - nextWidth - VIEWPORT_MARGIN);
      const left = Math.max(VIEWPORT_MARGIN, Math.min(preferredLeft, maxLeft));
      const spaceBelow = window.innerHeight - rect.bottom - offset - VIEWPORT_MARGIN;
      const spaceAbove = rect.top - offset - VIEWPORT_MARGIN;
      const naturalHeight = panelRef.current?.scrollHeight ?? 240;
      const openAbove = spaceBelow < naturalHeight && spaceAbove > spaceBelow;
      const availableHeight = Math.max(80, openAbove ? spaceAbove : spaceBelow);
      const nextMaxHeight = Math.min(window.innerHeight - VIEWPORT_MARGIN * 2, availableHeight);
      const panelHeight = Math.min(naturalHeight, nextMaxHeight);
      const top = openAbove
        ? rect.top - panelHeight - offset
        : rect.bottom + offset;

      setPanelWidth(nextWidth);
      setMaxHeight(nextMaxHeight);
      setPosition({ left, top: Math.max(VIEWPORT_MARGIN, top) });
    };

    const handleScroll = (event: Event) => {
      if (closeOnScroll && !panelRef.current?.contains(event.target as Node)) onClose();
      else updatePosition();
    };

    updatePosition();
    const frame = window.requestAnimationFrame(updatePosition);
    const resizeObserver = new ResizeObserver(updatePosition);
    if (panelRef.current) resizeObserver.observe(panelRef.current);
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', handleScroll, true);
    return () => {
      window.cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', handleScroll, true);
    };
  }, [align, anchor, closeOnScroll, offset, onClose, width]);

  useEffect(() => {
    if (!anchor) return;

    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (panelRef.current?.contains(target) || anchor.contains(target)) return;
      if (target instanceof Element && target.closest('[data-anchored-popover]')) return;
      onClose();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };

    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [anchor, onClose]);

  if (!anchor) return null;

  return createPortal(
    <div
      ref={panelRef}
      data-anchored-popover
      style={{
        left: position.left,
        top: position.top,
        width: panelWidth,
        maxHeight,
        zIndex,
        borderRadius,
        boxShadow: '0 12px 40px rgba(15, 23, 42, 0.14)',
      }}
      className="fixed overflow-x-hidden overflow-y-auto"
    >
      {children}
    </div>,
    document.body,
  );
}

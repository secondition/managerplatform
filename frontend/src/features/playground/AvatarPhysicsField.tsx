import { useLayoutEffect, useMemo, useRef } from 'react';
import type { PointerEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users } from 'lucide-react';
import type { UserBrief } from '@/types/api';
import { useDailySubscriptions, useOkrSubscriptions } from '@/features/subscription/hooks';
import { usePlaygroundStore } from '@/stores/playgroundStore';

// Bodies live in VIEWPORT coordinates: the floor is the bottom of the visible
// window, so blocks always rest at the bottom of whatever is on screen — the
// field is a fixed overlay that ignores page scroll entirely.
const BASE_SIZE = 56;         // square side at 0 collisions (px)
const MAX_SIZE = 176;         // cap so growth never destabilizes the physics
const HIT_GROWTH = 1;         // px added to the side per collision
const SEP_MARGIN = 6;         // gap past touching before a pair can re-collide
const GRAVITY = 2200;         // px/s^2
const REST = 0.55;            // bounce energy kept on impact
const WALL_TANGENT = 0.82;    // tangential damping when hitting a wall/floor
const AIR_DRAG = 0.4;         // fraction of velocity shed per second in air
const REST_EPS = 14;          // |vy| below this on the floor snaps to rest
const MAX_THROW = 2600;       // clamp for fling velocity (px/s)
const CLICK_MOVE = 6;         // travel (px) still treated as a click
const CLICK_MS = 260;         // press shorter than this treated as a click

type Body = {
  id: number;
  user: UserBrief;
  x: number; y: number;         // center in viewport px
  vx: number; vy: number;       // velocity (px/s)
  angle: number; spin: number;  // visual-only rotation (rad, rad/s)
  dragging: boolean;
  hits: number;                 // collisions this session; drives size
  size: number;                 // rendered side length (px) = BASE_SIZE + hits
};

const radiusOf = (b: Body) => b.size / 2;

type DragState = {
  id: number;
  pointerId: number;
  offX: number; offY: number;   // pointer offset from body center
  startX: number; startY: number; startT: number;
  lastX: number; lastY: number; lastT: number;
  vx: number; vy: number;       // smoothed pointer velocity
};

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
const rand = (lo: number, hi: number) => lo + Math.random() * (hi - lo);
const sizeFor = (hits: number) => clamp(BASE_SIZE + hits * HIT_GROWTH, BASE_SIZE, MAX_SIZE);
const pairKey = (a: number, b: number) => (a < b ? `${a}:${b}` : `${b}:${a}`);

export default function AvatarPhysicsField() {
  const enabled = usePlaygroundStore((s) => s.enabled);
  const toggleEnabled = usePlaygroundStore((s) => s.toggleEnabled);

  const okr = useOkrSubscriptions();
  const daily = useDailySubscriptions();

  // Union of OKR + daily subscriptions, deduped by user id.
  const users = useMemo(() => {
    const map = new Map<number, UserBrief>();
    for (const s of okr.data ?? []) map.set(s.target_user.id, s.target_user);
    for (const s of daily.data ?? []) map.set(s.target_user.id, s.target_user);
    return [...map.values()];
  }, [okr.data, daily.data]);

  return (
    <>
      <button
        onClick={toggleEnabled}
        title={enabled ? '收起订阅头像' : '展开订阅头像'}
        className={`fixed bottom-4 right-4 z-50 flex h-10 items-center gap-1.5 rounded-full px-3 text-xs font-medium shadow-lg transition-colors ${
          enabled ? 'bg-[var(--theme-accent)] text-white hover:bg-[var(--theme-accent-hover)]' : 'bg-white text-slate-500 hover:text-[var(--theme-accent)]'
        }`}
      >
        <Users size={14} />
        {users.length > 0 && <span className="font-mono tabular-nums">{users.length}</span>}
      </button>
      {enabled && users.length > 0 && <Field users={users} />}
    </>
  );
}

function Field({ users }: { users: UserBrief[] }) {
  const navigate = useNavigate();
  const bodiesRef = useRef<Map<number, Body>>(new Map());
  const elemsRef = useRef<Map<number, HTMLDivElement>>(new Map());
  const dragRef = useRef<DragState | null>(null);
  const seededRef = useRef(false);
  const hitsRef = useRef<Map<number, number>>(new Map());    // id -> collisions this session
  const contactRef = useRef<Set<string>>(new Set());         // pairs currently touching

  const bounds = () => ({ w: window.innerWidth, h: window.innerHeight });

  const paint = (b: Body) => {
    const el = elemsRef.current.get(b.id);
    if (!el) return;
    const r = radiusOf(b);
    // Keep the element's box in sync with its (growing) size.
    if (el.style.width !== `${b.size}px`) {
      el.style.width = `${b.size}px`;
      el.style.height = `${b.size}px`;
    }
    el.style.transform = `translate3d(${b.x - r}px, ${b.y - r}px, 0) rotate(${b.angle}rad)`;
  };

  // Reconcile bodies with the user list. First batch settles along the floor;
  // later additions (a fresh subscribe) drop from the center of the view.
  useLayoutEffect(() => {
    const { w, h } = bounds();
    const bodies = bodiesRef.current;
    const live = new Set(users.map((u) => u.id));
    for (const id of [...bodies.keys()]) if (!live.has(id)) bodies.delete(id);

    const firstSeed = !seededRef.current;
    users.forEach((user, i) => {
      const existing = bodies.get(user.id);
      if (existing) { existing.user = user; return; }
      const hits = hitsRef.current.get(user.id) ?? 0;
      const size = sizeFor(hits);
      const r = size / 2;
      const body: Body = firstSeed
        ? { id: user.id, user, x: clamp(rand(r, w - r), r, w - r), y: h - r - rand(0, h * 0.25), vx: rand(-120, 120), vy: 0, angle: 0, spin: 0, dragging: false, hits, size }
        : { id: user.id, user, x: w / 2 + rand(-40, 40) * i, y: h * 0.28, vx: rand(-160, 160), vy: 0, angle: rand(-0.4, 0.4), spin: rand(-4, 4), dragging: false, hits, size };
      bodies.set(user.id, body);
    });
    seededRef.current = true;
    bodies.forEach(paint);
  }, [users]);

  // Single rAF loop: integrate, resolve walls + pairwise collisions, paint.
  useLayoutEffect(() => {
    let raf = 0;
    let last = performance.now();

    const step = (now: number) => {
      const dt = Math.min(0.032, (now - last) / 1000);
      last = now;
      const { w, h } = bounds();
      const list = [...bodiesRef.current.values()];

      for (const b of list) {
        const r = radiusOf(b);
        if (b.dragging) { paint(b); continue; }

        b.vy += GRAVITY * dt;
        b.vx *= Math.max(0, 1 - AIR_DRAG * dt);
        b.x += b.vx * dt;
        b.y += b.vy * dt;
        b.angle += b.spin * dt;
        b.spin *= Math.max(0, 1 - 1.2 * dt);

        if (b.x < r) { b.x = r; b.vx = Math.abs(b.vx) * REST; b.vy *= WALL_TANGENT; }
        else if (b.x > w - r) { b.x = w - r; b.vx = -Math.abs(b.vx) * REST; b.vy *= WALL_TANGENT; }
        if (b.y < r) { b.y = r; b.vy = Math.abs(b.vy) * REST; }
        else if (b.y > h - r) {
          b.y = h - r;
          b.vx *= WALL_TANGENT;
          if (Math.abs(b.vy) < REST_EPS) { b.vy = 0; b.spin *= 0.6; }
          else b.vy = -Math.abs(b.vy) * REST;
        }
      }

      for (let i = 0; i < list.length; i++)
        for (let j = i + 1; j < list.length; j++) resolvePair(list[i], list[j], contactRef.current, countHit);

      for (const b of list) paint(b);
      raf = requestAnimationFrame(step);
    };

    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, []);

  // A fresh contact (two blocks that just started touching) grows both by 1px
  // and bumps each one's session collision count. contactRef gates repeats; the
  // size is capped by sizeFor(). Counts live only in memory — a reload resets.
  function countHit(a: Body, b: Body) {
    a.hits += 1;
    b.hits += 1;
    a.size = sizeFor(a.hits);
    b.size = sizeFor(b.hits);
    hitsRef.current.set(a.id, a.hits);
    hitsRef.current.set(b.id, b.hits);
  }

  // z-30 sits above page content (z-10) but below the sticky header (z-40). The
  // container is pointer-transparent; only the blocks capture the pointer.
  return (
    <div className="pointer-events-none fixed inset-0 z-30 overflow-hidden">
      {users.map((user) => (
        <AvatarBlock
          key={user.id}
          user={user}
          onRef={(el) => {
            if (el) elemsRef.current.set(user.id, el);
            else elemsRef.current.delete(user.id);
          }}
          onPointerDown={(e) => onPointerDown(e, user.id)}
          onPointerMove={onPointerMove}
          onPointerUp={(e) => onPointerUp(e, user.id)}
        />
      ))}
    </div>
  );

  function onPointerDown(e: PointerEvent<HTMLDivElement>, id: number) {
    const b = bodiesRef.current.get(id);
    if (!b) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    b.dragging = true;
    b.vx = 0; b.vy = 0; b.spin = 0;
    dragRef.current = {
      id, pointerId: e.pointerId,
      offX: e.clientX - b.x, offY: e.clientY - b.y,
      startX: e.clientX, startY: e.clientY, startT: performance.now(),
      lastX: e.clientX, lastY: e.clientY, lastT: performance.now(),
      vx: 0, vy: 0,
    };
  }

  function onPointerMove(e: PointerEvent<HTMLDivElement>) {
    const d = dragRef.current;
    if (!d || d.pointerId !== e.pointerId) return;
    const b = bodiesRef.current.get(d.id);
    if (!b) return;
    b.x = e.clientX - d.offX;
    b.y = e.clientY - d.offY;
    const dt = Math.max(0.001, (performance.now() - d.lastT) / 1000);
    // Exponential smoothing so the throw uses recent motion, not the whole drag.
    d.vx = 0.6 * d.vx + 0.4 * ((e.clientX - d.lastX) / dt);
    d.vy = 0.6 * d.vy + 0.4 * ((e.clientY - d.lastY) / dt);
    d.lastX = e.clientX; d.lastY = e.clientY; d.lastT = performance.now();
  }

  function onPointerUp(e: PointerEvent<HTMLDivElement>, id: number) {
    const d = dragRef.current;
    const b = bodiesRef.current.get(id);
    dragRef.current = null;
    if (b) b.dragging = false;
    if (!d || !b) return;
    const dist = Math.hypot(e.clientX - d.startX, e.clientY - d.startY);
    const held = performance.now() - d.startT;
    if (dist < CLICK_MOVE && held < CLICK_MS) { navigate(`/people/${id}`); return; }
    b.vx = clamp(d.vx, -MAX_THROW, MAX_THROW);
    b.vy = clamp(d.vy, -MAX_THROW, MAX_THROW);
    b.spin = clamp(b.vx / 220, -12, 12);
  }
}

// Impulse-based collision between two circle bodies. A dragged body acts as an
// immovable wall so the user can shove others around with the one they hold.
// `contact` tracks which pairs are currently touching so a single collision is
// counted once (on enter), not every frame; `onHit` fires on that first touch.
function resolvePair(a: Body, b: Body, contact: Set<string>, onHit: (a: Body, b: Body) => void) {
  const key = pairKey(a.id, b.id);
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const distSq = dx * dx + dy * dy;
  const min = radiusOf(a) + radiusOf(b);

  if (distSq >= (min + SEP_MARGIN) * (min + SEP_MARGIN)) contact.delete(key);
  if (distSq >= min * min || distSq === 0) return;

  const dist = Math.sqrt(distSq);
  const nx = dx / dist;
  const ny = dy / dist;
  const overlap = min - dist;

  const aFixed = a.dragging;
  const bFixed = b.dragging;

  // Count once per fresh contact — even if the pair is dragged into each other.
  if (!contact.has(key)) {
    contact.add(key);
    onHit(a, b);
  }
  if (aFixed && bFixed) return;

  if (aFixed) { b.x += nx * overlap; b.y += ny * overlap; }
  else if (bFixed) { a.x -= nx * overlap; a.y -= ny * overlap; }
  else {
    a.x -= nx * overlap * 0.5; a.y -= ny * overlap * 0.5;
    b.x += nx * overlap * 0.5; b.y += ny * overlap * 0.5;
  }

  const rvn = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny;
  if (rvn > 0) return;
  const jImpulse = -(1 + REST) * rvn / (aFixed || bFixed ? 1 : 2);
  const ix = jImpulse * nx;
  const iy = jImpulse * ny;
  if (!aFixed) { a.vx -= ix; a.vy -= iy; }
  if (!bFixed) { b.vx += ix; b.vy += iy; }
  const spinKick = (b.vx - a.vx) * 0.01;
  a.spin -= spinKick;
  b.spin += spinKick;
}

function AvatarBlock({
  user, onRef, onPointerDown, onPointerMove, onPointerUp,
}: {
  user: UserBrief;
  onRef: (el: HTMLDivElement | null) => void;
  onPointerDown: (e: PointerEvent<HTMLDivElement>) => void;
  onPointerMove: (e: PointerEvent<HTMLDivElement>) => void;
  onPointerUp: (e: PointerEvent<HTMLDivElement>) => void;
}) {
  return (
    <div
      ref={onRef}
      role="button"
      tabIndex={0}
      aria-label={`${user.name} 的主页`}
      title={`${user.name} · 拖拽或抛出，轻点进入主页`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      style={{ width: BASE_SIZE, height: BASE_SIZE, left: 0, top: 0, willChange: 'transform' }}
      className="pointer-events-auto absolute flex touch-none select-none items-center justify-center overflow-hidden rounded-2xl border border-white/70 bg-white active:cursor-grabbing"
    >
      <span className="flex h-full w-full items-center justify-center bg-[var(--theme-accent-soft)] text-base font-bold text-[var(--theme-accent)]">
        {user.name.slice(0, 2)}
      </span>
    </div>
  );
}

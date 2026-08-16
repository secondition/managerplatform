# Manager Platform Frontend

Frontend for the enterprise work-management platform: Feishu login, daily
reports, traffic-light weekly metrics, OKR, subscriptions, personal profiles,
and admin settings. React 18 + TypeScript + Vite + TanStack Query + Zustand +
Tailwind v4 + TipTap.

## Local setup

```bash
npm install
npm run dev
```

The dev server runs on http://localhost:5173 and proxies `/api` to the FastAPI
backend at http://127.0.0.1:8000. Start the backend first (see `../backend`).

Because everything is same-origin through the proxy, the backend's
`SameSite=Strict` httpOnly session cookies and CSRF double-submit work exactly
as they will in production (where FastAPI serves the built assets same-origin).

## Login

Single path: the login page renders Feishu's embedded QR code (the backend
builds the authorize URL from its `.env`). See `../飞书应用接入与配置指引.md`
for setting up the Feishu app.

## Scripts

- `npm run dev` — Vite dev server with API proxy
- `npm run build` — type-check (`tsc --noEmit`) then production build
- `npm run lint` — type-check only
- `npm run preview` — preview the production build

## Structure

```
src/
  app/router.tsx            # routes + auth/permission guards
  api/                       # typed API clients per backend module
  stores/authStore.ts       # user/permissions only (tokens stay in httpOnly cookies)
  types/api.ts  lib/{num,date}.ts
  components/{layout,ui,date,editor,user}/
  features/{auth,daily,traffic,okr,subscription,people,admin,settings}/
```

## Current scope

Live: 飞书登录, 工作日报, 红绿灯周指标, OKR 月度目标, 订阅日报,
订阅 OKR, 个人主页, 人员组, 后台员工/部门/AI 管理, 企业设置,
AI 日报评分, 今日建议, and OKR AI review.

Still placeholders: AI chat, notifications, inspiration list, and AI agents.

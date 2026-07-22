import { ShieldAlert } from 'lucide-react';

export default function ForbiddenPage() {
  return (
    <div className="max-w-md mx-auto py-20 text-center space-y-3">
      <div className="inline-flex p-3 bg-red-50 text-red-500 rounded-2xl">
        <ShieldAlert size={22} />
      </div>
      <h2 className="text-sm font-bold text-zinc-900">无访问权限</h2>
      <p className="text-xs text-zinc-500">
        你的账号没有查看该模块的权限，请联系管理员开通对应权限点。
      </p>
    </div>
  );
}

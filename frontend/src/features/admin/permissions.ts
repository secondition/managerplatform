// Permission points shown as toggles in the admin tables. Mirrors backend
// app/core/permissions. Feature points gate module availability (nav visibility
// + route access); advanced points gate the admin backend tabs.
export interface PermissionPoint {
  key: string;
  label: string;
}

export const FEATURE_POINTS: PermissionPoint[] = [
  { key: 'feature:daily', label: '日报' },
  { key: 'feature:traffic', label: '红绿灯' },
  { key: 'feature:okr', label: 'OKR' },
  { key: 'feature:group', label: '人员组' },
];

export const ADVANCED_POINTS: PermissionPoint[] = [
  { key: 'admin:employee', label: '员工管理' },
  { key: 'admin:department', label: '部门管理' },
  { key: 'admin:ai', label: '评分设置' },
  { key: 'admin:settings', label: '企业设置' },
];

// Any of these grants access to the admin backend (gear icon + /admin route).
export const ADVANCED_POINT_KEYS = ADVANCED_POINTS.map((p) => p.key);

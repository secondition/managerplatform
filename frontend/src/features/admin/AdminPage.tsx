import EmployeeList from './EmployeeList';
import AdvancedPermissions from './AdvancedPermissions';
import OrgManage from './OrgManage';
import AiConfigPage from './ai/AiConfigPage';
import CompanySettingsPage from '@/features/settings/CompanySettingsPage';
import ContactSyncHistory from './ContactSyncHistory';
import NotificationSettings from './NotificationSettings';
import AgentSettings from './AgentSettings';

export type AdminSection = 'employees' | 'sync-history' | 'permissions' | 'departments' | 'scoring' | 'agents' | 'settings' | 'notifications';

const SECTION_META: Record<AdminSection, { title: string; description: string }> = {
  notifications: {
    title: '通知设置',
    description: '按通知场景配置站内与飞书渠道，并查看飞书消息投递状态。',
  },
  employees: {
    title: '人员管理',
    description: '同步飞书通讯录，管理员工状态以及可使用的业务模块。',
  },
  'sync-history': {
    title: '通讯录同步记录',
    description: '查看飞书通讯录同步结果以及失败原因。',
  },
  permissions: {
    title: '权限管理',
    description: '配置员工进入各项后台管理能力的权限，仅 Owner 可操作。',
  },
  departments: {
    title: '部门管理',
    description: '维护当前公司的部门结构；人员组作为业务功能在工作台单独管理。',
  },
  scoring: {
    title: '评分设置',
    description: '配置评分服务商、模型、功能开关以及评分提示词。',
  },
  agents: {
    title: '智能体设置',
    description: '按员工或人员组配置智能体授权，并检查目标飞书群成员覆盖范围。',
  },
  settings: {
    title: '企业设置',
    description: '维护当前公司的名称、Logo 与平台展示信息。',
  },
};

export default function AdminPage({ section }: { section: AdminSection }) {
  const meta = SECTION_META[section];

  return (
    <div className="workspace-page space-y-4">
      <header>
        <h1 className="text-lg font-semibold text-slate-950">{meta.title}</h1>
        <p className="mt-1 text-xs leading-5 text-slate-500">{meta.description}</p>
      </header>

      {section === 'employees' && <EmployeeList />}
      {section === 'sync-history' && <ContactSyncHistory />}
      {section === 'permissions' && <AdvancedPermissions />}
      {section === 'departments' && <OrgManage show="department" />}
      {section === 'scoring' && <AiConfigPage />}
      {section === 'agents' && <AgentSettings />}
      {section === 'settings' && <CompanySettingsPage />}
      {section === 'notifications' && <NotificationSettings />}
    </div>
  );
}

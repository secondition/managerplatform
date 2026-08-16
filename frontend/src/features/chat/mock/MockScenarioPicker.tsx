import { FlaskConical } from 'lucide-react';
import {
  CHAT_MOCK_MESSAGE_VIEW_OPTIONS,
  CHAT_MOCK_SCENARIO_OPTIONS,
  type ChatMockMessageViewKey,
  type ChatMockScenarioKey,
} from './mockScenarios';

interface MockScenarioPickerProps {
  value: ChatMockScenarioKey;
  messageView: ChatMockMessageViewKey;
  messageViewEnabled: boolean;
  onChange: (scenario: ChatMockScenarioKey) => void;
  onMessageViewChange: (view: ChatMockMessageViewKey) => void;
}

export default function MockScenarioPicker({
  value,
  messageView,
  messageViewEnabled,
  onChange,
  onMessageViewChange,
}: MockScenarioPickerProps) {
  const current = CHAT_MOCK_SCENARIO_OPTIONS.find((option) => option.key === value);

  return (
    <div className="rounded-xl border border-dashed border-violet-200 bg-violet-50/70 px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-violet-700">
          <FlaskConical size={12} /> 前端状态预览
        </span>
        <select
          value={value}
          onChange={(event) => onChange(event.target.value as ChatMockScenarioKey)}
          aria-label="切换聊天模拟场景"
          className="min-h-7 rounded-lg border border-violet-200 bg-white px-2 text-[11px] text-slate-700 outline-none focus:border-violet-400"
        >
          {CHAT_MOCK_SCENARIO_OPTIONS.map((option) => (
            <option key={option.key} value={option.key}>
              {option.label}
            </option>
          ))}
        </select>
        <select
          value={messageView}
          disabled={!messageViewEnabled}
          onChange={(event) => onMessageViewChange(event.target.value as ChatMockMessageViewKey)}
          aria-label="切换消息展示场景"
          className="min-h-7 rounded-lg border border-violet-200 bg-white px-2 text-[11px] text-slate-700 outline-none disabled:cursor-not-allowed disabled:opacity-45 focus:border-violet-400"
        >
          {CHAT_MOCK_MESSAGE_VIEW_OPTIONS.map((option) => (
            <option key={option.key} value={option.key}>
              {option.label}
            </option>
          ))}
        </select>
        <span className="text-[10px] text-violet-500">{current?.description}</span>
      </div>
    </div>
  );
}

// Mirrors backend Pydantic schemas (app/schemas/*). Numeric fields serialized
// from Python Decimal may arrive as strings, so the traffic layer coerces them
// via lib/num before use.

export type Role = 'owner' | 'member';
export type Permission =
  | 'feature:daily'
  | 'feature:traffic'
  | 'feature:okr'
  | 'feature:group'
  | 'admin:employee'
  | 'admin:department'
  | 'admin:settings'
  | 'admin:ai';

export interface UserOut {
  id: number;
  name: string;
  email: string | null;
  avatar_url: string | null;
  role: Role;
  department_id: number | null;
  status: string;
  last_login_at: string | null;
}

export interface UserBrief {
  id: number;
  name: string;
  avatar_url: string | null;
  department_id: number | null;
}

// 人员组目录项：派发/成员选择器把组展开成 member_ids。
export interface GroupBrief {
  id: number;
  name: string;
  member_ids: number[];
}

export interface AuthUserResponse {
  user: UserOut;
  permissions: string[];
  csrf_token: string | null;
}

export interface FeishuLoginConfig {
  app_id: string;
  redirect_uri: string;
  state: string;
  // Full authorize URL built server-side (urlencoded); login page redirects here.
  authorize_url: string;
}

export interface CompanySettingOut {
  company_name: string;
  logo_url: string | null;
  footer_text: string;
}

// ---- Daily ----

export type RepeatRule = 'none' | 'daily' | 'weekly';

export interface DailyTaskOut {
  id: number;
  report_id: number;
  user_id: number;
  task_time: string; // "HH:MM:SS"
  content: string;
  note: string | null;
  is_private: boolean;
  is_done: boolean;
  done_at: string | null;
  repeat_rule: RepeatRule;
  source: string;
  assigned_to: number | null;
  assigned_by: number | null;
  sort_order: number;
  collaborators: UserBrief[];
  permission: 'owner' | 'collaborator' | 'follower';
  can_edit: boolean;
  can_delete: boolean;
  can_toggle_done: boolean;
  can_manage_members: boolean;
}

export interface ProblemSolutionOut {
  id: number;
  report_id: number;
  user_id: number;
  problem_text: string;
  solution_html: string | null;
  solution_json: Record<string, unknown> | unknown[] | null;
  search_text: string | null;
  sort_order: number;
}

export interface DailyReportOut {
  id: number | null;
  user_id: number;
  report_date: string; // YYYY-MM-DD
  status: string;
  tasks: DailyTaskOut[];
  problems: ProblemSolutionOut[];
}

export interface DailyRangeDayOut {
  date: string;
  tasks: DailyTaskOut[];
}

export interface DailySubscriptionOut {
  id: number;
  target_user: UserBrief;
  daily_enabled: boolean;
  okr_enabled: boolean;
  created_at: string;
}

export interface DailySubscriptionCandidateOut {
  user: UserBrief;
  subscribed: boolean;
}

export interface SubscribedDailyReportOut extends DailyReportOut {
  target_user: UserBrief;
}

export interface WeekDayOut {
  date: string; // YYYY-MM-DD
  has_content: boolean;
}

// ---- People / profile ----

export interface PersonUserOut {
  id: number;
  name: string;
  email: string | null;
  avatar_url: string | null;
  profile_signature: string | null;
  role: Role;
  department_id: number | null;
  department_name: string | null;
  status: string;
  last_login_at: string | null;
  last_synced_at: string | null;
}

export interface PersonSubscriptionOut {
  subscribed: boolean;
  daily_enabled: boolean;
  okr_enabled: boolean;
}

export interface PersonSocialOut {
  followers_count: number;
  following_count: number;
}

export interface PersonAiScoreOut {
  status: 'not_ready' | 'ready' | string;
  score: number | null;
  summary: string | null;
  updated_at: string | null;
}

export type PersonCalendarState = 'none' | 'missing' | 'done';

export interface PersonCalendarDayOut {
  date: string;
  is_workday: boolean;
  is_future: boolean;
  has_daily: boolean;
  state: PersonCalendarState;
}

export interface PersonMonthlyDailyOut {
  month: string;
  done_days: number;
  missing_days: number;
  required_days: number;
  task_completion_rate: number | null;
  completed_tasks: number;
  total_tasks: number;
  days: PersonCalendarDayOut[];
}

export interface PersonProfileOut {
  user: PersonUserOut;
  is_self: boolean;
  subscription: PersonSubscriptionOut;
  social: PersonSocialOut;
  daily_score: PersonAiScoreOut;
  okr_review: PersonAiScoreOut;
  daily_calendar: PersonMonthlyDailyOut;
}

// ---- Traffic light ----

export type MetricDirection = 'increase' | 'decrease';
// Per-week status: on_target = 达标(绿), missed = 未达标(红), empty = 未填(灰).
export type ValueStatus = 'on_target' | 'missed' | 'empty';

export interface WeekColumnOut {
  week_index: number; // ISO week number
  label: string;
  week_start: string;
  week_end: string;
  is_empty: boolean;
}

export type MetricRole = 'owner' | 'editor' | 'viewer';

export interface TrafficMetricValueOut {
  id: number;
  metric_id: number;
  week_start: string;
  week_end: string;
  value: string | number | null;
  status: 'on_target' | 'missed';
  note: string | null;
}

export interface TrafficMetricMemberOut {
  user_id: number;
  name: string;
  avatar_url: string | null;
  role: 'editor' | 'viewer';
}

export interface TrafficMetricOut {
  id: number;
  owner_id: number;
  name: string;
  unit: string | null;
  direction: MetricDirection;
  weekly_target: string | number | null;
  north_star_target: string | number | null;
  sort_order: number;
  values: TrafficMetricValueOut[]; // only weeks inside the current window
  recent_avg: string | number | null;
  status: ValueStatus;
  members: TrafficMetricMemberOut[];
  my_role: MetricRole;
  can_edit_values: boolean;
  can_edit_meta: boolean;
  can_manage_members: boolean;
  can_delete: boolean;
  is_pending: boolean;
}

// ---- OKR ------------------------------------------------------------------

export interface KeyResultProgressOut {
  id: number;
  key_result_id: number;
  user_id: number;
  note: string;
  progress_date: string;
  created_at: string;
}

export interface OkrCommentOut {
  id: number;
  objective_id: number | null;
  key_result_id: number | null;
  content: string;
  author: {
    id: number;
    name: string;
    avatar_url: string | null;
  };
  created_at: string;
  updated_at: string;
  can_edit: boolean;
}

export interface KeyResultOut {
  id: number;
  objective_id: number;
  title: string;
  progress: string | number; // 0..100, manually marked by the KR slider
  sort_order: number;
  comment_count: number;
  progress_updates: KeyResultProgressOut[];
}

export interface ObjectiveOut {
  id: number;
  user_id: number;
  month: string; // YYYY-MM
  title: string;
  progress: string | number;
  sort_order: number;
  comment_count: number;
  key_results: KeyResultOut[];
}

export interface MonthlyReportSectionOut {
  id: number;
  month: string;
  section_key: 'performance' | 'innovation' | string;
  title: string;
  content_html: string | null;
  content_json: string | null; // TipTap JSON serialized as a string
  sort_order: number;
}

export interface OkrReviewOut {
  status: 'empty' | 'ready';
  generated_at: string | null;
  quality_score: string | number | null;
  summary: string | null;
}

export interface OkrMonthOut {
  month: string;
  objectives: ObjectiveOut[];
  monthly_report: MonthlyReportSectionOut[];
  review: OkrReviewOut;
}

// ---- OKR subscriptions ----------------------------------------------------

export interface OkrSubscriptionOut {
  id: number;
  target_user: UserBrief;
  daily_enabled: boolean;
  okr_enabled: boolean;
  created_at: string;
}

export interface OkrSubscriptionCandidateOut {
  user: UserBrief;
  subscribed: boolean;
}

export interface SubscribedOkrMonthOut extends OkrMonthOut {
  target_user: UserBrief;
}

// ---- AI ------------------------------------------------------------------

export type AiStatus = 'ready' | 'empty' | 'not_enabled';

export interface ScoreDimension {
  name: string;
  score: number;
  full: number;
  comment: string | null;
}

export interface DailyScoreOut {
  status: AiStatus;
  score_date: string | null;
  total_score: number | null;
  level: string | null;
  score_delta: number | null;
  trend_note: string | null;
  one_line_review: string | null;
  dimensions: ScoreDimension[];
  okr_outside_high_value: string[];
  okr_outside_ratio: string;
  manager_hint: string | null;
  okr_clarity_warning: string | null;
  generated_at: string | null;
}

export interface WeeklyScoreOut {
  status: AiStatus;
  week_start: string | null;
  week_end: string | null;
  total_score: number | null;
  level: string | null;
  summary: string | null;
  dimensions: ScoreDimension[];
  key_achievements: string[];
  concerns: string[];
  manager_hint: string | null;
  generated_at: string | null;
}

export interface DailySuggestionOut {
  id: number;
  suggestion_date: string;
  content: string;
  reason: string | null;
  suggestion_type: 'red' | 'amber' | 'blue' | 'green';
  linked: {
    my_kr?: string;
    others?: string;
  };
  needs_info: boolean;
  ask: {
    question?: string;
    options?: string[];
  };
  status: 'pending' | 'accepted' | 'rejected';
  accepted_task_id: number | null;
}

export interface DailySuggestionListOut {
  status: AiStatus;
  summary: string;
  items: DailySuggestionOut[];
}

export interface OkrImprovementOut {
  target: string;
  point: string;
  suggestion: string;
}

export interface OkrReviewFullOut {
  status: AiStatus;
  month: string | null;
  total_score: string | number | null;
  level: string | null;
  summary: string | null;
  dimensions: ScoreDimension[];
  highlights: string[];
  optional_improvements: OkrImprovementOut[];
  impact_on_daily_scoring: string | null;
  generated_at: string | null;
}

export interface MonthlyReportScoreOut {
  status: AiStatus;
  month: string | null;
  total_score: number | null;
  summary: string | null;
  dimensions: ScoreDimension[];
  doubts: string[];
  suggestions: string[];
  generated_at: string | null;
}

// ---- Admin AI config -----------------------------------------------------

export type AiProviderKind = 'openai_chat' | 'openai_response' | 'anthropic' | 'openai_compatible' | 'deepseek' | 'openai';

export interface AiProviderOut {
  provider: string;
  api_base: string;
  default_model: string;
  enabled: boolean;
  api_key_masked: string;
  api_key_set: boolean;
}

export interface AiProviderTestOut {
  ok: boolean;
  message: string;
}

export interface AiFeatureFlagsOut {
  daily_score_enabled: boolean;
  daily_suggestion_enabled: boolean;
  okr_review_enabled: boolean;
  scheduler_enabled: boolean;
}

export interface PromptVariable {
  key: string;
  label: string;
  description: string;
}

export interface PromptConfigOut {
  id: number;
  prompt_type:
    | 'daily_score'
    | 'weekly_score'
    | 'daily_suggestion'
    | 'okr_quality'
    | 'monthly_report_score';
  name: string;
  template_content: string;
  version: string;
  variables: string[];
  available_variables: PromptVariable[];
}

export interface AiTaskOut {
  id: number;
  user_id: number | null;
  task_type: string;
  status: 'pending' | 'running' | 'succeeded' | 'failed';
  error_message: string | null;
  model: string | null;
  ref_date: string | null;
  ref_month: string | null;
  started_at: string | null;
  finished_at: string | null;
}



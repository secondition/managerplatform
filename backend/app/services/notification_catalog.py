from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationTypeDefinition:
    type: str
    label: str
    description: str
    in_app_default: bool
    feishu_default: bool


NOTIFICATION_TYPES = (
    NotificationTypeDefinition("daily.assigned", "日报任务派发", "收到他人派发的日报任务", True, True),
    NotificationTypeDefinition(
        "daily.collaborator_added", "日报协作者添加", "成为日报任务的协作者", True, True
    ),
    NotificationTypeDefinition("subscription.started", "订阅开始", "他人开始订阅我的内容", True, True),
    NotificationTypeDefinition("subscription.ended", "订阅结束", "他人取消订阅我的内容", True, False),
    NotificationTypeDefinition("daily.score_ready", "日报评分完成", "日报 AI 评分生成完成", True, False),
    NotificationTypeDefinition(
        "daily.suggestion_ready", "日报建议完成", "日报 AI 建议生成完成", True, True
    ),
    NotificationTypeDefinition("weekly.score_ready", "周评分完成", "周 AI 评分生成完成", True, False),
    NotificationTypeDefinition("okr.review_ready", "OKR 复盘完成", "OKR AI 复盘生成完成", True, False),
    NotificationTypeDefinition(
        "monthly_report.score_ready", "月报评分完成", "月报 AI 评分生成完成", True, False
    ),
    NotificationTypeDefinition("daily.missing", "日报未填写", "每天 10:00 和 17:00 检查", True, True),
    NotificationTypeDefinition(
        "traffic.weekly_metric_missing", "周指标未填写", "每周一检查上一完整周", True, True
    ),
)

NOTIFICATION_TYPE_MAP = {item.type: item for item in NOTIFICATION_TYPES}

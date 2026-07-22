from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.okr import (
    MonthlyReportSection,
    OkrComment,
    OkrKeyResult,
    OkrKeyResultProgress,
    OkrObjective,
)
from app.models.user import User
from app.schemas.okr import (
    KeyResultCreate,
    KeyResultProgressCreate,
    KeyResultUpdate,
    MonthlyReportSectionUpdate,
    ObjectiveCreate,
    ObjectiveUpdate,
    OkrCommentCreate,
    OkrCommentUpdate,
)
from app.utils.html_sanitize import sanitize_html
from app.core.security import utcnow

_HUNDRED = Decimal("100")
_ZERO = Decimal("0")
# Default monthly report sections, created lazily on first access.
_DEFAULT_SECTIONS = [
    ("performance", "业绩相关"),
    ("innovation", "本月创新"),
]


class OkrService:
    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user

    # ---- month aggregate ---------------------------------------------------

    def get_month(self, month: str) -> dict:
        objectives = self._list_objectives(month, self.user.id)
        sections = self._ensure_sections(month)
        return {
            "month": month,
            "objectives": [self._serialize_objective(o) for o in objectives],
            "monthly_report": [self._serialize_section(s) for s in sections],
            "review": self._review_summary(month, self.user.id),
        }

    def get_month_readonly(self, month: str, target_user_id: int) -> dict:
        """Read another user's OKR month for the subscription (follower) view.

        No lazy section creation — followers only see sections the target has
        actually created. Callers must verify the subscription first.
        """
        objectives = self._list_objectives(month, target_user_id)
        sections = self._list_sections(month, target_user_id)
        return {
            "month": month,
            "objectives": [self._serialize_objective(o) for o in objectives],
            "monthly_report": [self._serialize_section(s) for s in sections],
            "review": self._review_summary(month, target_user_id),
        }

    def _review_summary(self, month: str, user_id: int) -> dict:
        """Light review summary for the OKR month payload (full detail via /okr/review)."""
        from app.models.ai import OkrReview

        row = self.db.scalar(
            select(OkrReview).where(
                OkrReview.user_id == user_id,
                OkrReview.month == month,
                OkrReview.deleted_at.is_(None),
            )
        )
        if row is None or not row.level:
            return {"status": "empty", "generated_at": None, "quality_score": None, "summary": None}
        return {
            "status": "ready",
            "generated_at": row.generated_at.isoformat() if row.generated_at else None,
            "quality_score": row.quality_score,
            "summary": row.summary,
        }

    def _list_objectives(self, month: str, user_id: int) -> list[OkrObjective]:
        return list(
            self.db.scalars(
                select(OkrObjective)
                .options(
                    selectinload(OkrObjective.comments),
                    selectinload(OkrObjective.key_results).selectinload(OkrKeyResult.comments),
                    selectinload(OkrObjective.key_results).selectinload(OkrKeyResult.progress_updates),
                )
                .where(
                    OkrObjective.user_id == user_id,
                    OkrObjective.month == month,
                    OkrObjective.deleted_at.is_(None),
                )
                .order_by(OkrObjective.sort_order, OkrObjective.id)
            ).all()
        )

    def _list_sections(self, month: str, user_id: int) -> list[MonthlyReportSection]:
        return list(
            self.db.scalars(
                select(MonthlyReportSection)
                .where(
                    MonthlyReportSection.user_id == user_id,
                    MonthlyReportSection.month == month,
                    MonthlyReportSection.deleted_at.is_(None),
                )
                .order_by(MonthlyReportSection.sort_order, MonthlyReportSection.id)
            ).all()
        )

    # ---- objectives --------------------------------------------------------

    def create_objective(self, payload: ObjectiveCreate) -> dict:
        objective = OkrObjective(
            user_id=self.user.id,
            month=payload.month,
            title=payload.title.strip(),
            sort_order=self._next_objective_sort(payload.month),
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        self.db.add(objective)
        self.db.flush()
        for idx, kr in enumerate(payload.key_results):
            objective.key_results.append(self._build_kr(objective.id, kr, idx))
        self.db.flush()
        self._recalculate_objective_progress(objective)
        self.db.commit()
        return self._serialize_objective(self._get_objective(objective.id))

    def update_objective(self, objective_id: int, payload: ObjectiveUpdate) -> dict:
        objective = self._get_objective(objective_id)
        if "title" in payload.model_fields_set:
            if payload.title is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="title cannot be null")
            objective.title = payload.title.strip()
        objective.updated_by = self.user.id
        self.db.commit()
        return self._serialize_objective(self._get_objective(objective_id))

    def reorder_objectives(self, month: str, ids: list[int]) -> dict:
        objectives = self._list_objectives(month, self.user.id)
        by_id = {objective.id: objective for objective in objectives}
        if len(ids) != len(set(ids)) or set(ids) != set(by_id):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ids must contain all objectives in this month exactly once")
        for sort_order, objective_id in enumerate(ids, start=1):
            objective = by_id[objective_id]
            objective.sort_order = sort_order
            objective.updated_by = self.user.id
        self.db.commit()
        return self.get_month(month)

    def delete_objective(self, objective_id: int) -> None:
        objective = self._get_objective(objective_id)
        now = utcnow()
        objective.deleted_at = now
        objective.updated_by = self.user.id
        for kr in objective.key_results:
            if kr.deleted_at is None:
                kr.deleted_at = now
                kr.updated_by = self.user.id
            for update in kr.progress_updates:
                if update.deleted_at is None:
                    update.deleted_at = now
                    update.updated_by = self.user.id
            for comment in kr.comments:
                if comment.deleted_at is None:
                    comment.deleted_at = now
                    comment.updated_by = self.user.id
        for comment in objective.comments:
            if comment.deleted_at is None:
                comment.deleted_at = now
                comment.updated_by = self.user.id
        self.db.commit()

    # ---- key results -------------------------------------------------------

    def add_key_result(self, objective_id: int, payload: KeyResultCreate) -> dict:
        objective = self._get_objective(objective_id)
        idx = self._next_kr_sort(objective)
        objective.key_results.append(self._build_kr(objective.id, payload, idx))
        self.db.flush()
        self._recalculate_objective_progress(objective)
        self.db.commit()
        return self._serialize_objective(self._get_objective(objective_id))

    def update_key_result(self, kr_id: int, payload: KeyResultUpdate) -> dict:
        kr = self._get_kr(kr_id)
        recalculate_progress = False
        for field in ("title", "progress"):
            if field not in payload.model_fields_set:
                continue
            value = getattr(payload, field)
            if value is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{field} cannot be null",
                )
            if field == "progress":
                value = self._clamp_progress(value)
                recalculate_progress = True
            setattr(kr, field, value.strip() if isinstance(value, str) else value)
        kr.updated_by = self.user.id
        if recalculate_progress:
            objective = self._get_objective(kr.objective_id)
            self._recalculate_objective_progress(objective)
        self.db.commit()
        return self._serialize_objective(self._get_objective(kr.objective_id))

    def reorder_key_results(self, objective_id: int, ids: list[int]) -> dict:
        objective = self._get_objective(objective_id)
        active = [kr for kr in objective.key_results if kr.deleted_at is None]
        by_id = {kr.id: kr for kr in active}
        if len(ids) != len(set(ids)) or set(ids) != set(by_id):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ids must contain all key results exactly once")
        for sort_order, kr_id in enumerate(ids, start=1):
            kr = by_id[kr_id]
            kr.sort_order = sort_order
            kr.updated_by = self.user.id
        self.db.commit()
        return self._serialize_objective(self._get_objective(objective_id))

    def delete_key_result(self, kr_id: int) -> dict:
        kr = self._get_kr(kr_id)
        objective_id = kr.objective_id
        kr.deleted_at = utcnow()
        kr.updated_by = self.user.id
        for update in kr.progress_updates:
            if update.deleted_at is None:
                update.deleted_at = kr.deleted_at
                update.updated_by = self.user.id
        for comment in kr.comments:
            if comment.deleted_at is None:
                comment.deleted_at = kr.deleted_at
                comment.updated_by = self.user.id
        objective = self._get_objective(objective_id)
        self._recalculate_objective_progress(objective)
        self.db.commit()
        return self._serialize_objective(self._get_objective(objective_id))

    def _build_kr(self, objective_id: int, payload: KeyResultCreate, sort_order: int) -> OkrKeyResult:
        kr = OkrKeyResult(
            objective_id=objective_id,
            title=payload.title.strip(),
            progress=self._clamp_progress(payload.progress),
            sort_order=sort_order,
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        return kr

    # ---- progress history --------------------------------------------------

    def list_key_result_progress(self, kr_id: int) -> list[OkrKeyResultProgress]:
        self._get_kr(kr_id)
        return list(
            self.db.scalars(
                select(OkrKeyResultProgress)
                .where(
                    OkrKeyResultProgress.key_result_id == kr_id,
                    OkrKeyResultProgress.deleted_at.is_(None),
                )
                .order_by(
                    OkrKeyResultProgress.progress_date.desc(),
                    OkrKeyResultProgress.created_at.desc(),
                    OkrKeyResultProgress.id.desc(),
                )
            ).all()
        )

    def create_key_result_progress(
        self,
        kr_id: int,
        payload: KeyResultProgressCreate,
    ) -> OkrKeyResultProgress:
        kr = self._get_kr(kr_id)
        objective = self._get_objective(kr.objective_id)
        if payload.progress_date.strftime("%Y-%m") != objective.month:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="progress_date must belong to the objective month",
            )

        record = OkrKeyResultProgress(
            key_result_id=kr.id,
            user_id=self.user.id,
            progress_date=payload.progress_date,
            note=payload.note,
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    # ---- comments ----------------------------------------------------------

    def list_objective_comments(self, objective_id: int) -> list[dict]:
        self._get_objective(objective_id)
        return self._list_comments(objective_id=objective_id)

    def list_key_result_comments(self, kr_id: int) -> list[dict]:
        self._get_kr(kr_id)
        return self._list_comments(key_result_id=kr_id)

    def create_objective_comment(self, objective_id: int, payload: OkrCommentCreate) -> dict:
        self._get_objective(objective_id)
        return self._create_comment(payload, objective_id=objective_id)

    def create_key_result_comment(self, kr_id: int, payload: OkrCommentCreate) -> dict:
        self._get_kr(kr_id)
        return self._create_comment(payload, key_result_id=kr_id)

    def update_comment(self, comment_id: int, payload: OkrCommentUpdate) -> dict:
        comment = self._get_comment(comment_id)
        comment.content = payload.content
        comment.updated_by = self.user.id
        self.db.commit()
        return self._serialize_comment(self._get_comment(comment_id))

    def delete_comment(self, comment_id: int) -> None:
        comment = self._get_comment(comment_id)
        comment.deleted_at = utcnow()
        comment.updated_by = self.user.id
        self.db.commit()

    def _list_comments(
        self,
        *,
        objective_id: int | None = None,
        key_result_id: int | None = None,
    ) -> list[dict]:
        target = (
            OkrComment.objective_id == objective_id
            if objective_id is not None
            else OkrComment.key_result_id == key_result_id
        )
        rows = self.db.scalars(
            select(OkrComment)
            .options(selectinload(OkrComment.author))
            .where(target, OkrComment.deleted_at.is_(None))
            .order_by(OkrComment.created_at, OkrComment.id)
        ).all()
        return [self._serialize_comment(row) for row in rows]

    def _create_comment(
        self,
        payload: OkrCommentCreate,
        *,
        objective_id: int | None = None,
        key_result_id: int | None = None,
    ) -> dict:
        comment = OkrComment(
            objective_id=objective_id,
            key_result_id=key_result_id,
            user_id=self.user.id,
            content=payload.content,
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        self.db.add(comment)
        self.db.commit()
        return self._serialize_comment(self._get_comment(comment.id))

    def _get_comment(self, comment_id: int) -> OkrComment:
        comment = self.db.scalar(
            select(OkrComment)
            .options(selectinload(OkrComment.author))
            .where(OkrComment.id == comment_id, OkrComment.deleted_at.is_(None))
        )
        if comment is None or comment.user_id != self.user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
        if comment.objective_id is not None:
            self._get_objective(comment.objective_id)
        elif comment.key_result_id is not None:
            self._get_kr(comment.key_result_id)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment target not found")
        return comment

    # ---- monthly report ----------------------------------------------------

    def update_section(self, section_id: int, payload: MonthlyReportSectionUpdate) -> dict:
        section = self.db.scalar(
            select(MonthlyReportSection).where(
                MonthlyReportSection.id == section_id,
                MonthlyReportSection.deleted_at.is_(None),
            )
        )
        if section is None or section.user_id != self.user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
        if "title" in payload.model_fields_set:
            if payload.title is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="title cannot be null")
            section.title = payload.title.strip()
        if "content_html" in payload.model_fields_set:
            section.content_html = sanitize_html(payload.content_html) if payload.content_html is not None else None
        if "content_json" in payload.model_fields_set:
            section.content_json = payload.content_json
        section.updated_by = self.user.id
        self.db.commit()
        section = self.db.get(MonthlyReportSection, section_id)
        return self._serialize_section(section)

    def _ensure_sections(self, month: str) -> list[MonthlyReportSection]:
        existing = list(
            self.db.scalars(
                select(MonthlyReportSection)
                .where(
                    MonthlyReportSection.user_id == self.user.id,
                    MonthlyReportSection.month == month,
                    MonthlyReportSection.deleted_at.is_(None),
                )
                .order_by(MonthlyReportSection.sort_order, MonthlyReportSection.id)
            ).all()
        )
        present = {s.section_key for s in existing}
        created = False
        for idx, (key, title) in enumerate(_DEFAULT_SECTIONS):
            if key not in present:
                self.db.add(
                    MonthlyReportSection(
                        user_id=self.user.id,
                        month=month,
                        section_key=key,
                        title=title,
                        sort_order=idx,
                        created_by=self.user.id,
                        updated_by=self.user.id,
                    )
                )
                created = True
        if created:
            self.db.commit()
            return self._ensure_sections(month)
        return existing

    # ---- progress ----------------------------------------------------------

    def _clamp_progress(self, value: Decimal) -> Decimal:
        return max(_ZERO, min(_HUNDRED, value)).quantize(Decimal("0.01"))

    def _recalculate_objective_progress(self, objective: OkrObjective) -> None:
        active = [kr for kr in objective.key_results if kr.deleted_at is None]
        if not active:
            objective.progress = _ZERO
        else:
            total = sum((kr.progress for kr in active), _ZERO)
            objective.progress = (total / Decimal(len(active))).quantize(Decimal("0.01"))
        objective.updated_by = self.user.id

    # ---- fetch helpers -----------------------------------------------------

    def _get_objective(self, objective_id: int) -> OkrObjective:
        objective = self.db.scalar(
            select(OkrObjective)
            .options(
                selectinload(OkrObjective.comments),
                selectinload(OkrObjective.key_results).selectinload(OkrKeyResult.comments),
                selectinload(OkrObjective.key_results).selectinload(OkrKeyResult.progress_updates),
            )
            .where(OkrObjective.id == objective_id, OkrObjective.deleted_at.is_(None))
        )
        if objective is None or objective.user_id != self.user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objective not found")
        return objective

    def _get_kr(self, kr_id: int) -> OkrKeyResult:
        kr = self.db.scalar(
            select(OkrKeyResult)
            .options(
                selectinload(OkrKeyResult.comments),
                selectinload(OkrKeyResult.progress_updates),
            )
            .where(OkrKeyResult.id == kr_id, OkrKeyResult.deleted_at.is_(None))
        )
        if kr is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key result not found")
        # Ownership through the parent objective.
        self._get_objective(kr.objective_id)
        return kr

    def _next_objective_sort(self, month: str) -> int:
        value = self.db.scalar(
            select(func.max(OkrObjective.sort_order)).where(
                OkrObjective.user_id == self.user.id,
                OkrObjective.month == month,
                OkrObjective.deleted_at.is_(None),
            )
        )
        return int(value or 0) + 1

    def _next_kr_sort(self, objective: OkrObjective) -> int:
        active = [k.sort_order for k in objective.key_results if k.deleted_at is None]
        return (max(active) + 1) if active else 1

    # ---- serialization -----------------------------------------------------

    def _serialize_objective(self, objective: OkrObjective) -> dict:
        krs = sorted(
            (k for k in objective.key_results if k.deleted_at is None),
            key=lambda k: (k.sort_order, k.id),
        )
        return {
            "id": objective.id,
            "user_id": objective.user_id,
            "month": objective.month,
            "title": objective.title,
            "progress": objective.progress,
            "sort_order": objective.sort_order,
            "comment_count": sum(1 for c in objective.comments if c.deleted_at is None),
            "key_results": [
                {
                    "id": k.id,
                    "objective_id": k.objective_id,
                    "title": k.title,
                    "progress": k.progress,
                    "sort_order": k.sort_order,
                    "comment_count": sum(1 for c in k.comments if c.deleted_at is None),
                    "progress_updates": [
                        self._serialize_progress(update)
                        for update in sorted(
                            (u for u in k.progress_updates if u.deleted_at is None),
                            key=lambda u: (u.progress_date, u.created_at, u.id),
                            reverse=True,
                        )
                    ],
                }
                for k in krs
            ],
        }

    def _serialize_progress(self, record: OkrKeyResultProgress) -> dict:
        return {
            "id": record.id,
            "key_result_id": record.key_result_id,
            "user_id": record.user_id,
            "note": record.note,
            "progress_date": record.progress_date,
            "created_at": record.created_at,
        }

    def _serialize_comment(self, comment: OkrComment) -> dict:
        return {
            "id": comment.id,
            "objective_id": comment.objective_id,
            "key_result_id": comment.key_result_id,
            "content": comment.content,
            "author": {
                "id": comment.author.id,
                "name": comment.author.name,
                "avatar_url": comment.author.avatar_url,
            },
            "created_at": comment.created_at,
            "updated_at": comment.updated_at,
            "can_edit": comment.user_id == self.user.id,
        }

    def _serialize_section(self, section: MonthlyReportSection) -> dict:
        return {
            "id": section.id,
            "month": section.month,
            "section_key": section.section_key,
            "title": section.title,
            "content_html": section.content_html,
            "content_json": section.content_json,
            "sort_order": section.sort_order,
        }

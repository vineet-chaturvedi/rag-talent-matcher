"""
Feedback from the people who use the portal (Step 14c): thumbs up or down on a match result or an agent answer,
with an optional reason and comment.

Why keep it: every click is a LABELLED EXAMPLE ("for this role, this person is / isn't a match"; "this answer
was wrong because it named the wrong people"). Labels are what evaluation and tuning need (Step 14d), and
only real use produces enough of them.

Design:
- One rating per person per item: rating again changes it (no double votes).
- For a match result, the role and the employee are stored too, so the label survives when the run is
  deleted or re-run ("Priya is a good match for the Kubernetes role" stays true).
- `context` is a SNAPSHOT of what the person saw (rank, score, requirements; or the question, answer and
  tool calls), because the answer or run may later be deleted and the label must still make sense.
"""
from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, enum_column
from app.db.enums import FeedbackRating, FeedbackTarget


class Feedback(TimestampMixin, Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target: Mapped[FeedbackTarget] = mapped_column(enum_column(FeedbackTarget), index=True)
    rating: Mapped[FeedbackRating] = mapped_column(enum_column(FeedbackRating))
    reason: Mapped[str | None] = mapped_column(String(40))
    comment: Mapped[str | None] = mapped_column(Text)

    # target = match_result
    match_result_id: Mapped[int | None] = mapped_column(ForeignKey("match_results.id", ondelete="SET NULL"))
    match_run_id: Mapped[int | None] = mapped_column(ForeignKey("match_runs.id", ondelete="SET NULL"))
    role_id: Mapped[int | None] = mapped_column(ForeignKey("project_roles.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    # target = agent_answer
    agent_message_id: Mapped[int | None] = mapped_column(ForeignKey("agent_messages.id", ondelete="SET NULL"))

    context: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("user_id", "match_result_id", name="uq_feedback_user_result"),
        UniqueConstraint("user_id", "agent_message_id", name="uq_feedback_user_message"),
    )

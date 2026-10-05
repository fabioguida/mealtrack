"""Email composition and sending.

Backends: ConsoleBackend prints (development, tests, and keeps an outbox);
SesBackend sends through Amazon SES with the instance's role. Content is
rendered from templates/emails/<kind>.txt and .html.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.deps import templates
from app.models import EmailLog, NotificationSettings, User
from app.progress import progress_for
from app.shopping import shopping_list


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    text: str
    html: str


class ConsoleBackend:
    name = "console"

    def __init__(self):
        self.outbox: list[Message] = []

    def send(self, msg: Message) -> None:
        self.outbox.append(msg)
        print(f"--- email to {msg.to}: {msg.subject}\n{msg.text}\n")


class SesBackend:
    name = "ses"

    def __init__(self):
        import boto3

        self.client = boto3.client("sesv2")

    def send(self, msg: Message) -> None:
        self.client.send_email(
            FromEmailAddress=config.EMAIL_FROM,
            Destination={"ToAddresses": [msg.to]},
            Content={"Simple": {
                "Subject": {"Data": msg.subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": msg.text, "Charset": "UTF-8"}, "Html": {"Data": msg.html, "Charset": "UTF-8"}},
            }},
        )


_backend = None


def get_backend():
    global _backend
    if _backend is None:
        _backend = SesBackend() if config.EMAIL_BACKEND == "ses" else ConsoleBackend()
    return _backend


def settings_for(db: Session, user: User) -> NotificationSettings:
    row = db.get(NotificationSettings, user.id)
    return row or NotificationSettings(user_id=user.id, daily_shopping=True, weekly_shopping=True, progress=True)


# --- composition ---------------------------------------------------------------

def _render(kind: str, ctx: dict) -> tuple[str, str, str]:
    ctx = {**ctx, "app_url": config.APP_URL}
    subject = templates.env.get_template(f"emails/{kind}.subject.txt").render(ctx).strip()
    text = templates.env.get_template(f"emails/{kind}.txt").render(ctx)
    html = templates.env.get_template(f"emails/{kind}.html").render(ctx)
    return subject, text, html


def compose_daily(db: Session, user: User, today: date) -> Message | None:
    """The evening mail: tomorrow's shopping list and today's progress."""
    s = settings_for(db, user)
    tomorrow = today + timedelta(days=1)
    groups = shopping_list(db, user, tomorrow, tomorrow) if s.daily_shopping else []
    progress = progress_for(db, user, today) if s.progress else None
    if not groups and progress is None:
        return None
    subject, text, html = _render("daily", {"user": user, "today": today, "tomorrow": tomorrow, "groups": groups, "progress": progress})
    return Message(user.email, subject, text, html)


def compose_weekly(db: Session, user: User, saturday: date) -> Message | None:
    """The Saturday mail: next week's shopping list (Mon–Sun) and the week behind."""
    s = settings_for(db, user)
    monday = saturday + timedelta(days=(7 - saturday.weekday()) % 7 or 7)  # next Monday
    sunday = monday + timedelta(days=6)
    groups = shopping_list(db, user, monday, sunday) if s.weekly_shopping else []
    progress = progress_for(db, user, saturday - timedelta(days=1)) if s.progress else None
    if not groups and progress is None:
        return None
    subject, text, html = _render("weekly", {"user": user, "saturday": saturday, "monday": monday, "sunday": sunday, "groups": groups, "progress": progress})
    return Message(user.email, subject, text, html)


# --- sending with the log ----------------------------------------------------------

def send_logged(db: Session, user: User, kind: str, period: str, msg: Message | None) -> str:
    """Send once per (user, kind, period); returns sent | failed | skipped | duplicate."""
    if db.scalar(select(EmailLog).where(EmailLog.user_id == user.id, EmailLog.kind == kind, EmailLog.period == period)):
        return "duplicate"
    if msg is None:
        db.add(EmailLog(user_id=user.id, kind=kind, period=period, status="skipped", detail="nothing to send"))
        db.commit()
        return "skipped"
    try:
        get_backend().send(msg)
        status, detail = "sent", msg.subject[:255]
    except Exception as exc:  # the log keeps the reason; cron tries again next period
        status, detail = "failed", f"{type(exc).__name__}: {exc}"[:255]
    db.add(EmailLog(user_id=user.id, kind=kind, period=period, status=status, detail=detail, sent_at=datetime.now()))
    db.commit()
    return status


def send_daily_to_all(db: Session, today: date) -> dict[str, int]:
    counts: dict[str, int] = {}
    for user in db.scalars(select(User).where(User.password_hash.is_not(None))):
        r = send_logged(db, user, "daily", today.isoformat(), compose_daily(db, user, today))
        counts[r] = counts.get(r, 0) + 1
    return counts


def send_weekly_to_all(db: Session, saturday: date) -> dict[str, int]:
    counts: dict[str, int] = {}
    for user in db.scalars(select(User).where(User.password_hash.is_not(None))):
        r = send_logged(db, user, "weekly", saturday.isoformat(), compose_weekly(db, user, saturday))
        counts[r] = counts.get(r, 0) + 1
    return counts

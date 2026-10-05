"""Email composition and sending.

Backends: ConsoleBackend prints (development, tests, and keeps an outbox);
SesBackend sends through Amazon SES with the instance's role. Content is
rendered from templates/emails/<kind>.*; the opening line and the milestones
come from data/email_phrases_it.json.

The evening mail changes shape with the user's situation: a normal day gets
tomorrow's shopping list and the progress; after two days without a logged
meal it becomes a short "come back" note, weekly after seven days, and stops
after thirty (one last line). Never more than one email a day.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.deps import templates
from app.models import EmailLog, NotificationSettings, User
from app.phrases import phrase
from app.progress import ProgressSummary, progress_for
from app.shopping import shopping_list

COMEBACK_AFTER_DAYS = 2
WEEKLY_AFTER_DAYS = 7
STOP_AFTER_DAYS = 30


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


def register_recipient(email: str) -> None:
    """While the SES account is in the sandbox, a recipient must be a verified
    identity: registering the address at sign-up makes AWS send the user its
    verification email right away. Harmless once production access is granted
    (and a no-op with the console backend)."""
    if config.EMAIL_BACKEND != "ses":
        return
    try:
        import boto3

        boto3.client("sesv2").create_email_identity(EmailIdentity=email)
    except Exception as exc:  # already registered, no permission, offline: never block sign-up
        print(f"ses identity for {email} not created: {type(exc).__name__}")


_backend = None


def get_backend():
    global _backend
    if _backend is None:
        _backend = SesBackend() if config.EMAIL_BACKEND == "ses" else ConsoleBackend()
    return _backend


def settings_for(db: Session, user: User) -> NotificationSettings:
    row = db.get(NotificationSettings, user.id)
    return row or NotificationSettings(user_id=user.id, daily_shopping=True, weekly_shopping=True, progress=True, weekly_only=False)


# --- the human lines -------------------------------------------------------------

def first_name(user: User) -> str:
    return user.email.split("@")[0].split(".")[0].capitalize()


def opening_line(user: User, p: ProgressSummary | None, day: date) -> str:
    if p is None:
        return ""
    t = p.today
    values = {"name": first_name(user), "streak": p.streak, "days": p.days_since_log}
    if t.eaten_kcal is not None:
        values["over"] = int(round(max(0.0, t.eaten_kcal - t.allowed_kcal)))
        values["left"] = int(round(max(0.0, t.allowed_kcal - t.eaten_kcal)))
    return phrase(p.situation, f"{day}:{user.id}", **values)


def milestone_lines(user: User, p: ProgressSummary | None, day: date) -> list[str]:
    if p is None:
        return []
    kg = (p.first_weight[1] - p.weights[-1][1]) if (p.first_weight and p.weights) else 0.0
    return [l for l in (phrase(m, f"{day}:{user.id}", name=first_name(user), streak=p.streak, kg=f"{kg:.1f}") for m in p.milestones) if l]


MASCOTS = {"on_target": "happy", "under": "happy", "over": "sweaty", "no_log": "sleepy"}


def mascot_for(p: ProgressSummary | None, milestones: list[str]) -> str | None:
    """The plate-face at the top of the mail (static/img/email/face-*.png): party on a
    milestone, otherwise it follows today's situation; none without a progress."""
    if p is None:
        return None
    return "party" if milestones else MASCOTS[p.situation]


# --- composition -----------------------------------------------------------------

def _render(kind: str, ctx: dict) -> tuple[str, str, str]:
    ctx = {**ctx, "app_url": config.APP_URL}
    subject = templates.env.get_template(f"emails/{kind}.subject.txt").render(ctx).strip()
    text = templates.env.get_template(f"emails/{kind}.txt").render(ctx)
    html = templates.env.get_template(f"emails/{kind}.html").render(ctx)
    return subject, text, html


def compose_daily(db: Session, user: User, today: date) -> Message | None:
    """The evening mail, shaped by the situation; None when nothing should go out."""
    s = settings_for(db, user)
    if s.weekly_only:
        return None
    tomorrow = today + timedelta(days=1)
    progress = progress_for(db, user, today)
    away = progress.days_since_log if progress else 0

    if progress is not None and away >= COMEBACK_AFTER_DAYS:
        if away > STOP_AFTER_DAYS:
            return None
        if away == STOP_AFTER_DAYS:
            situation = "goodbye"
        elif away >= WEEKLY_AFTER_DAYS:
            if away % 7 != 0:
                return None
            situation = "comeback_long"
        else:
            situation = "comeback_short"
        line = phrase(situation, f"{today}:{user.id}", name=first_name(user), days=away)
        subject, text, html = _render("comeback", {"user": user, "today": today, "tomorrow": tomorrow, "line": line,
                                                   "tomorrow_meals": progress.tomorrow_meals, "goodbye": situation == "goodbye",
                                                   "mascot": "sleepy"})
        return Message(user.email, subject, text, html)

    groups = shopping_list(db, user, tomorrow, tomorrow) if s.daily_shopping else []
    progress = progress if s.progress else None
    if not groups and progress is None:
        return None
    milestones = milestone_lines(user, progress, today)
    subject, text, html = _render("daily", {
        "user": user, "today": today, "tomorrow": tomorrow, "groups": groups, "progress": progress,
        "line": opening_line(user, progress, today), "milestones": milestones, "mascot": mascot_for(progress, milestones),
    })
    return Message(user.email, subject, text, html)


def compose_weekly(db: Session, user: User, saturday: date) -> Message | None:
    """The Saturday mail: next week's shopping list (Mon–Sun) and the week behind."""
    s = settings_for(db, user)
    monday = saturday + timedelta(days=(7 - saturday.weekday()) % 7 or 7)  # next Monday
    sunday = monday + timedelta(days=6)
    groups = shopping_list(db, user, monday, sunday) if (s.weekly_shopping or s.weekly_only) else []
    progress = progress_for(db, user, saturday - timedelta(days=1)) if (s.progress or s.weekly_only) else None
    if progress is not None and progress.days_since_log > STOP_AFTER_DAYS:
        return None  # gone for good, as far as we know: silence
    if not groups and progress is None:
        return None
    milestones = milestone_lines(user, progress, saturday - timedelta(days=1))
    subject, text, html = _render("weekly", {
        "user": user, "saturday": saturday, "monday": monday, "sunday": sunday, "groups": groups, "progress": progress,
        "line": phrase("weekly_open", f"{saturday}:{user.id}", name=first_name(user)),
        "milestones": milestones, "mascot": "party" if milestones else ("happy" if progress else None),
    })
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

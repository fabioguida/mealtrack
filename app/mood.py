"""The app's mood: the plate-face mascot, the line of the day, the streak and
the milestones. Shared by the Oggi page, the weight page and the emails so
they speak with one voice (phrases in data/email_phrases_it.json)."""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from app.models import User
from app.phrases import phrase
from app.progress import ProgressSummary, progress_for

MASCOTS = {"on_target": "happy", "under": "happy", "over": "sweaty", "no_log": "sleepy"}
STREAK_SHOW_FROM = 2


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


def mascot_for(p: ProgressSummary | None, milestones: list[str]) -> str | None:
    """party on a milestone, otherwise the day's situation; none without a progress."""
    if p is None:
        return None
    return "party" if milestones else MASCOTS[p.situation]


@dataclass
class Mood:
    situation: str
    mascot: str
    line: str
    streak: int
    milestones: list[str] = field(default_factory=list)
    kg_lost: float | None = None

    @property
    def celebrate(self) -> bool:
        return bool(self.milestones)

    @property
    def show_streak(self) -> bool:
        return self.streak >= STREAK_SHOW_FROM


def mood_for(db: Session, user: User, day: date) -> Mood | None:
    p = progress_for(db, user, day)
    if p is None:
        return None
    milestones = milestone_lines(user, p, day)
    kg = (p.first_weight[1] - p.weights[-1][1]) if (p.first_weight and p.weights) else None
    return Mood(p.situation, mascot_for(p, milestones) or "happy", opening_line(user, p, day), p.streak, milestones, kg)

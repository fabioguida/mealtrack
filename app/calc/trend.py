"""Weekly feedback: the trend is judged, not the single day (HANDOVER.md feature 8).

The average is taken over the logged days of the window (a day without any
meal is not a zero-kcal day, it is a day not logged). Each day is compared to
its own ceiling (target + activity), so the average is of the daily balance
ratios' numerators and denominators: eaten / allowed over the window.
"""

from dataclasses import dataclass

TOLERANCE = 0.05  # ±5 % of the target counts as "in linea"
MIN_DAYS = 3


@dataclass(frozen=True)
class WeekTrend:
    logged_days: int
    eaten_avg: float
    allowed_avg: float
    verdict: str  # "pochi_dati", "in_linea", "sopra", "sotto"

    @property
    def text(self) -> str:
        if self.verdict == "pochi_dati":
            return "Registra almeno tre giorni per vedere l'andamento della settimana."
        if self.verdict == "in_linea":
            return "In linea con il target: un giorno sopra non è un errore se la media tiene."
        if self.verdict == "sopra":
            diff = self.eaten_avg - self.allowed_avg
            return f"Sopra il target di circa {diff:.0f} kcal al giorno: sistema i prossimi giorni, senza saltare pasti."
        diff = self.allowed_avg - self.eaten_avg
        return f"Sotto il target di circa {diff:.0f} kcal al giorno: va bene se ti senti in forze, altrimenti mangia un po' di più."


def weekly_trend(days: list[tuple[float | None, float]]) -> WeekTrend:
    """`days` holds (kcal eaten or None if not logged, kcal allowed) per day."""
    logged = [(e, a) for e, a in days if e is not None]
    if len(logged) < MIN_DAYS:
        return WeekTrend(len(logged), 0.0, 0.0, "pochi_dati")
    eaten = sum(e for e, _ in logged) / len(logged)
    allowed = sum(a for _, a in logged) / len(logged)
    if allowed <= 0:
        verdict = "pochi_dati"
    elif eaten > allowed * (1 + TOLERANCE):
        verdict = "sopra"
    elif eaten < allowed * (1 - TOLERANCE):
        verdict = "sotto"
    else:
        verdict = "in_linea"
    return WeekTrend(len(logged), eaten, allowed, verdict)

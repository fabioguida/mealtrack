"""Send the scheduled emails to every user (run by cron on the server).

Usage: python scripts/send_emails.py daily|weekly [YYYY-MM-DD]
  daily   the evening mail for the given day (default today): tomorrow's shopping, today's progress
  weekly  the Saturday mail (default today): next week's shopping, last week's progress

Each (user, kind, period) is sent once: rerunning is safe.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.db import engine
from app.emails import send_daily_to_all, send_weekly_to_all

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("daily", "weekly"):
        sys.exit(__doc__)
    day = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
    with Session(engine) as db:
        counts = send_daily_to_all(db, day) if sys.argv[1] == "daily" else send_weekly_to_all(db, day)
    print(f"{date.today().isoformat()} {sys.argv[1]} {day.isoformat()}: {counts}")

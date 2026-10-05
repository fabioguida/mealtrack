"""Set or reset a user's password (admin, no email recovery yet).

Usage: python scripts/set_password.py <email>   (the password is asked, not echoed)
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.db import engine
from app.models import User

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    email = sys.argv[1].strip().lower()
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            sys.exit(f"Nessun utente con email {email}")
        pw = getpass.getpass("Nuova password: ")
        if len(pw) < 8:
            sys.exit("Almeno 8 caratteri.")
        user.password_hash = hash_password(pw)
        db.commit()
    print(f"Password aggiornata per {email}")

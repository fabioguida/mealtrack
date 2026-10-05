# Meal Tracker

Web app di famiglia per tracciare pasti, macronutrienti, peso e attività fisica rispetto all'obiettivo di ogni utente.

Stack: Python + FastAPI, SQLite, template Jinja + HTMX. Hosting su AWS (EC2 + S3).

Documenti:

- [HANDOVER.md](HANDOVER.md): specifica vincolante, decisioni prese e aperte, ordine di sviluppo. Leggere per primo.
- [PLAN.md](PLAN.md): piano di sviluppo in nove fasi, con i test di ogni fase e le scoperte fatte costruendo.
- [ARCHITECTURE.md](ARCHITECTURE.md): sintesi dell'architettura.
- [PIANO_ALIMENTARE.md](PIANO_ALIMENTARE.md): piano dell'autore, usato come dati di prova del primo utente.

## Avvio locale

```
.venv\Scripts\python scripts\init_db.py          # tabelle + primo utente (SEED_USER_EMAIL / SEED_USER_PASSWORD in .env)
.venv\Scripts\python scripts\import_foods.py     # alimenti generici
.venv\Scripts\python -m uvicorn app.main:app --reload
```

## Alimenti

La tabella degli alimenti è fatta di cibi generici, non di prodotti confezionati:

- `data/foods_swiss_it.csv`: i 1 216 alimenti generici della **Banca dati svizzera dei valori nutritivi** (Ufficio federale della sicurezza alimentare e di veterinaria, https://naehrwertdaten.ch/it/), edizione italiana, estratti dal file Excel ufficiale con `scripts/extract_swiss.py`. Uso libero, anche in app, con citazione della fonte (riportata nel piè di pagina).
- `data/foods_extra_it.csv`: alimenti italiani che la banca dati svizzera non ha (orata, branzino, yogurt greco, mozzarella di bufala, cannellini, passata...), con valori approssimati da CREA o da etichette, indicati riga per riga e **da verificare**.
- Gli alimenti creati dagli utenti (`/alimenti/nuovo`) sono visibili solo a chi li ha creati.

La ricerca lavora per inizio di parola, in qualsiasi ordine e senza accenti ("petto pollo", "caffe"), e mostra prima gli alimenti base e poi i piatti pronti.

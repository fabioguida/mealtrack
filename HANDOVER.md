# Handover — Meal Tracker Web App

Documento di passaggio per continuare lo sviluppo in Claude Code.
Data: 5 ottobre 2026. Specifica completa (doc condiviso): https://claude.ai/code/artifact/8dd8da83-fceb-45b6-8c4a-f346c0dbfec2

> Istruzione per Claude Code: leggi tutto questo file prima di scrivere codice. Le sezioni "Decisioni prese" sono vincolanti; le "Decisioni aperte" vanno chiarite con l'utente prima di implementarle. Il frontend deve seguire le convenzioni del repo GitHub esistente dell'utente (vedi sezione 7).

---

## 1. Obiettivo

Web app per tracciare pasti, macronutrienti, peso e attività fisica, e dire a ogni utente se sta andando bene rispetto al suo obiettivo (dimagrimento).

- **Utenti:** l'autore, la sua famiglia, qualche amico. Uso familiare, non pubblico.
- **Piattaforma:** solo web, usata anche da telefono via browser (layout responsive obbligatorio).
- **Sviluppatore:** l'utente è uno sviluppatore Python; sviluppa con Claude Code.

---

## 2. Decisioni prese

| Area | Decisione | Note |
| --- | --- | --- |
| Backend | Python + FastAPI | |
| Database | SQLite all'inizio | Migrazione a Postgres/RDS solo se l'app cresce |
| Frontend | Template Jinja renderizzati dal server + HTMX | Niente React/Vue. Stile e struttura come il repo GitHub esistente |
| Autenticazione | Email + password, password con hash | Niente verifica email, niente 2FA per ora |
| Multi-utente | Sì, ogni tabella ha `user_id` | Ogni utente vede solo i propri dati |
| Database alimenti | USDA FoodData Central, scaricato e importato una volta | Piatti italiani mancanti aggiunti a mano come alimenti `custom` |
| Macro tracciati | Calorie, proteine, carboidrati, grassi | Proteine obbligatorie fin dall'inizio |
| Attività fisica | Riduce il bilancio: le kcal bruciate alzano il tetto del giorno | Stima con valori MET |
| Feedback | Valutato sulla media settimanale, non sul singolo giorno | |
| Foto pasti | Archiviate su AWS S3, versioning attivo | |
| Backup | Settimanale, copia del DB su S3, conservazione massima 2 mesi | Circa 8 copie; le più vecchie cancellate da una lifecycle rule |
| Hosting | AWS, account esistente dell'utente, configurazione più economica | App e DB sulla stessa piccola istanza EC2 |
| Costi | Obiettivo: il minimo possibile | Il free tier AWS dei 12 mesi è scaduto (account con più di un anno) |

---

## 3. Modello dati

Ogni tabella (tranne `foods` con `source = usda`) ha `user_id`.

| Tabella | Campi principali |
| --- | --- |
| `users` | `id`, `email` (unica), `password_hash`, `created_at` |
| `profiles` | `user_id`, `age`, `height_cm`, `sex`, `activity_level`, `goal` (mantenere/dimagrire), target giornalieri calcolati |
| `foods` | `id`, `name`, `source` (`usda` / `custom`), `owner_user_id` (solo per custom), `kcal`, `protein_g`, `carbs_g`, `fat_g` — tutti per 100 g |
| `meals` | `id`, `user_id`, `datetime`, `meal_type` (colazione/pranzo/spezzafame/cena), `photo_url` (opzionale), `input_method` (`photo` / `manual` / `preset`) |
| `meal_items` | `id`, `meal_id`, `food_id`, `grams`, valori calcolati |
| `weights` | `id`, `user_id`, `date`, `kg` |
| `workouts` | `id`, `user_id`, `date`, `activity` (palestra, corsa, camminata, tennis…), `duration_min`, `kcal_burned` |
| `meal_presets` | `id`, `user_id`, `name`, voci (alimento + grammi) |
| `eating_schedules` | `user_id`, `day_of_week`, orari dei pasti (colazione, pranzo, spezzafame, cena o nessuna), quota di kcal per pasto |
| `meal_plans` | `id`, `user_id`, `start_date`, `weeks` (default 2), `kcal_target`, `protein_target_g` usati per generarlo |
| `meal_plan_items` | `id`, `plan_id`, `date`, `meal_type`, `food_id`, `grams`, kcal e macro calcolati |
| `food_preferences` | `user_id`, `food_id` o categoria, `like` / `dislike` / `avoid` (es. "niente cioccolato fondente") |

Il peso attuale si legge dall'ultima riga di `weights`, non da `profiles`: così il fabbisogno si ricalcola a ogni nuova pesata.

---

## 4. Funzionalità

1. **Inserimento pasto, due ingressi, un solo motore.** Foto (l'AI stima alimenti e grammi) oppure inserimento manuale. Entrambi producono una lista `[(food_id, grams)]` che passa allo stesso motore di calcolo. **Implementare prima il manuale.**
2. **Correzione delle stime.** Dopo una stima da foto l'utente può correggere alimenti e grammi prima di salvare.
3. **Libreria personale (senza addestrare modelli).** I pasti corretti vengono salvati; quando arriva un pasto simile, l'app propone le porzioni abituali dell'utente. Decisione esplicita: niente fine-tuning, servirebbero molti più esempi di quelli disponibili.
4. **Preset per i pasti ricorrenti.** Pasti fissi salvati con le quantità e richiamati con un tocco.
5. **Bilancio giornaliero**, dall'alto in basso:
   - barra calorie grande: verde dentro il target, rossa se sforato, con indicazione di quanto resta;
   - barra proteine da riempire (target per kg di peso);
   - barre carboidrati e grassi più piccole, affiancate, solo informative;
   - lista dei pasti di oggi con miniatura della foto, toccabili per correggere.
6. **Attività.** Ogni allenamento registrato aggiunge le kcal stimate al target di quel giorno.
7. **Pesate.** Registro del peso nel tempo; il fabbisogno si ricalcola automaticamente.
8. **Feedback settimanale.** Un giorno sopra target non è un errore se la media della settimana è in linea.
9. **Piano alimentare per utente, con quantità in grammi.** Ogni utente ha il suo piano di due settimane, non quello dell'autore. Il piano nasce da tre input dell'utente:
   - **orari** (`eating_schedules`): finestra di digiuno, quali pasti fa, regole diverse per i giorni del weekend;
   - **preferenze** (`food_preferences`): cosa gli piace e cosa esclude;
   - **target** dal profilo: kcal e proteine del giorno.

   Ogni pasto del piano ha alimenti **con i grammi**, calcolati così:
   1. kcal del pasto = target del giorno × quota del pasto (es. colazione 30%, pranzo 45%, spezzafame 25%; quote configurabili per utente);
   2. si parte da un piatto modello (preset o piatto della libreria) con proporzioni fisse tra gli ingredienti;
   3. si scala tutto il piatto per raggiungere le kcal del pasto, poi si controlla che le proteine del giorno arrivino al target; se no, si aumenta la parte proteica e si riduce quella di carboidrati;
   4. i grammi si arrotondano a valori pratici (es. multipli di 5 g; unità intere per uova, frutti, fette di pane).

   Il piano si rigenera quando cambia il peso o il target. Nel bilancio giornaliero, i pasti del piano compaiono come suggerimento da confermare con un tocco.

---

## 5. Formule

**Metabolismo basale (Mifflin-St Jeor)**, peso in kg, altezza in cm, età in anni:

- uomo: `BMR = 10 × peso + 6,25 × altezza − 5 × età + 5`
- donna: `BMR = 10 × peso + 6,25 × altezza − 5 × età − 161`

**Fabbisogno:** `TDEE = BMR × fattore di attività` (fattori standard da 1,2 sedentario a circa 1,9 molto attivo).

**Target dimagrimento:** `TDEE − deficit`. Nella discussione si è usato 500 kcal/giorno come esempio: rendere il deficit configurabile, non fisso nel codice.

**Calorie da attività (MET):** `kcal = MET × peso_kg × ore`. Valori MET da una tabella di riferimento (es. Compendium of Physical Activities), uno per tipo di attività.

**Proteine:** nella discussione si è indicato circa 1,5 g per kg di peso. Valore da verificare e lasciare configurabile.

> L'app mostra stime, non prescrizioni mediche. Aggiungere una nota visibile in tal senso.

---

## 6. Infrastruttura AWS

- **Calcolo:** una piccola istanza EC2 con app + SQLite.
- **File:** bucket S3 per le foto dei pasti, versioning attivo.
- **Backup:**
  - job settimanale (cron sull'istanza) che crea una copia consistente del DB con l'API di backup di SQLite (`sqlite3 app.db ".backup backup.db"`), **non** una semplice copia del file mentre è in scrittura;
  - upload su S3 sotto un prefisso dedicato (es. `backups/`);
  - lifecycle rule S3 che cancella gli oggetti in `backups/` dopo 60 giorni.
- **Costi:** le cifre emerse a voce (circa 10–20 $/mese per l'istanza più piccola, RDS dai 15 $ in su) erano stime a memoria, **non verificate**. Controllare sul calcolatore prezzi AWS prima di scegliere il tipo di istanza.

---

## 7. Note per Claude Code

- **Stile del frontend:** l'utente ha un sito recente in un suo repo GitHub. Prima di scrivere il frontend, chiedere all'utente quale repo, leggerlo e seguirne struttura, convenzioni e stile grafico. Questa specifica non li descrive.
- **Ordine di sviluppo consigliato:**
  1. modello dati + import USDA;
  2. inserimento manuale dei pasti + motore di calcolo;
  3. bilancio giornaliero (pagina con le 4 barre);
  4. autenticazione e profili;
  5. pesate e attività;
  6. preset e libreria personale;
  7. piano alimentare per utente con quantità (funzionalità 9);
  8. analisi foto (dopo aver chiuso la decisione aperta 8.1);
  9. deploy su AWS + backup.
- Tenere tutto semplice: è un'app di famiglia.

---

## 8. Decisioni aperte

### 8.1 Analisi delle foto dei pasti

Quale modello AI legge le foto e stima i grammi.

- L'abbonamento Claude Pro/Max dell'utente **non** copre le chiamate automatiche fatte dall'app. Serve una chiave API, fatturata a parte a consumo.
- Costo per immagine da verificare sulla pagina prezzi ufficiale prima di decidere.
- Alternativa: rilasciare solo l'inserimento manuale e aggiungere le foto dopo.

### 8.2 Dati del profilo

Le quantità e i target dipendono da età, altezza, peso, sesso e livello di attività di ogni utente. Li inserisce ogni utente nel suo profilo.

### 8.3 Come si scelgono i piatti del piano

Le quantità si calcolano con le regole della funzionalità 9. Resta da decidere **chi sceglie quali piatti** vanno in ogni giorno:

- **Regole (consigliato per partire):** rotazione dei piatti modello della libreria, con vincoli semplici (es. pasta 2 volte a settimana, pesce 2, legumi 2), filtrati dalle preferenze. Gratis e prevedibile.
- **AI:** l'AI propone i piatti, il codice calcola comunque i grammi. Più vario, ma ha un costo API (stesso discorso di 8.1).

In entrambi i casi i grammi li calcola sempre il codice, non l'AI, così i numeri tornano con i target.

### 8.4 Quote dei pasti e arrotondamenti

Le quote di esempio (30/45/25%) e gli arrotondamenti sono proposte, non valori verificati. Renderli configurabili e farli confermare all'utente.

### 8.5 Varie (non discusse, da chiarire se servono)

- Lingua dell'interfaccia (probabilmente italiano).
- Dominio e HTTPS.
- Recupero password.

---

## 9. Contesto: il piano alimentare dell'autore

L'autore segue un piano di digiuno intermittente (16:8). Nell'app è **solo il suo profilo**, non un default per tutti: ogni utente imposta i propri orari e preferenze. Utile come dati di prova per il primo utente:

- **Lun–Gio:** colazione 7:30, pranzo 13:30, spezzafame 15:30, niente cena.
- **Ven–Sab:** pranzo leggero, niente spezzafame, cena fuori.
- **Domenica:** pranzo in famiglia, niente cena.
- **Pasti ricorrenti** (candidati preset): avocado toast su pane integrale con uova strapazzate; yogurt greco con avena e frutta; porridge; spezzafame frutta + mandorle oppure yogurt greco + frutta.

Il piano attuale non ha grammi (mancavano i dati del profilo): sarà l'app a calcolarli. Il piano completo è in un documento separato: https://claude.ai/code/artifact/0a683b92-2cf7-4403-acc6-6d95d512f46a

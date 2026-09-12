# Life RPG — Full-Stack Productivity RPG

A full-stack Flask application that turns real-world tasks into RPG quests. Users create quests, complete them to earn server-calculated XP and Gold, level up through a non-linear progression curve, build character attributes, maintain streaks, and purchase virtual rewards.

## Stack

- Python 3.11+
- Flask 3.1
- SQLite (real database persistence)
- Server-side sessions + Werkzeug password hashing
- HTML/CSS/JavaScript (responsive and accessible UI)

## Core scenarios implemented

1. Secure signup/login/logout.
2. Per-user quest CRUD (create and delete from UI; status is changed through server-side completion flow).
3. Non-linear XP leveling.
4. Category-specific attributes.
5. Consecutive-day activity streak.
6. Gold economy and persistent shop inventory.
7. Celebratory completion/level-up animations.
8. Database persistence across page refreshes and devices when using the same deployed database.
9. Responsive navigation, keyboard-friendly controls, semantic landmarks and labels.
10. Error handling for bad requests and missing resources.

## Run locally on Windows

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SECRET_KEY="replace-with-a-long-random-secret"
python app.py
```

Open: http://127.0.0.1:5000

## Run locally on macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="replace-with-a-long-random-secret"
python app.py
```

## Database

The SQLite database is created automatically as `life_rpg.db` on first run. Do not delete it if you want persistence. The application does not use localStorage as its primary data store.

## Production notes

For a real deployment, set a strong `SECRET_KEY`, keep `DATABASE` on persistent storage, run Flask behind a production WSGI server such as Gunicorn, and use HTTPS. On platforms that use ephemeral disks, SQLite is not suitable for durable production storage unless a persistent volume is configured; PostgreSQL is the better production upgrade.

## Suggested Git history

Create at least three meaningful chronological commits, for example:

```text
feat: add Flask auth and database schema
feat: add quest, XP, streak and attribute engine
feat: add RPG UI, shop and responsive animations
```

## 90–180 second demo flow

1. Sign up.
2. Create a quest such as “Complete 2 coding problems”.
3. Complete it.
4. Show XP, Gold, attribute increase and streak.
5. Complete enough quests to trigger a level up.
6. Open the Shop and purchase an item.
7. Refresh the page and show that the character data, quest history and inventory persist.

## Production deployment helper files

- `Procfile` runs the app with Gunicorn on platforms that support Procfiles.
- `render.yaml` provides a Render service template and generated `SECRET_KEY`.
- For durable multi-instance production storage, replace SQLite with PostgreSQL and set `DATABASE` to a durable connection/storage strategy.

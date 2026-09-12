import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.getenv("DATABASE", os.path.join(BASE_DIR, "life_rpg.db"))
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

CATEGORY_MAP = {
    "coding": ("Intellect", "🧠"),
    "study": ("Knowledge", "📚"),
    "fitness": ("Strength", "💪"),
    "mindfulness": ("Focus", "🧘"),
    "reading": ("Wisdom", "📖"),
    "other": ("Discipline", "⚡"),
}

DIFFICULTY_REWARDS = {
    "easy": {"xp": 30, "gold": 10},
    "medium": {"xp": 60, "gold": 22},
    "hard": {"xp": 110, "gold": 40},
    "epic": {"xp": 180, "gold": 70},
}

SHOP_ITEMS = [
    ("neon", "Neon Grid", "Cyberpunk grid theme", "theme", 150, "🌌"),
    ("ember", "Ember Core", "Warm energy theme", "theme", 250, "🔥"),
    ("aether", "Aether Sky", "Calm futuristic theme", "theme", 350, "☁️"),
    ("nova", "Nova Badge", "Badge for consistent progress", "badge", 200, "✨"),
    ("titan", "Titan Badge", "Badge for completing hard quests", "badge", 500, "👑"),
    ("focus", "Focus Badge", "Badge for mindfulness quests", "badge", 300, "🎯"),
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            xp INTEGER NOT NULL DEFAULT 0,
            level INTEGER NOT NULL DEFAULT 1,
            gold INTEGER NOT NULL DEFAULT 0,
            streak INTEGER NOT NULL DEFAULT 0,
            last_activity TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS attributes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            intellect INTEGER NOT NULL DEFAULT 1,
            knowledge INTEGER NOT NULL DEFAULT 1,
            strength INTEGER NOT NULL DEFAULT 1,
            focus INTEGER NOT NULL DEFAULT 1,
            wisdom INTEGER NOT NULL DEFAULT 1,
            discipline INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            xp_reward INTEGER NOT NULL,
            gold_reward INTEGER NOT NULL,
            completed_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            quest_id INTEGER,
            activity_date TEXT NOT NULL,
            xp_earned INTEGER NOT NULL DEFAULT 0,
            gold_earned INTEGER NOT NULL DEFAULT 0,
            category TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (quest_id) REFERENCES quests(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_key TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            item_type TEXT NOT NULL,
            price INTEGER NOT NULL,
            icon TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            purchased_at TEXT NOT NULL,
            UNIQUE(user_id, item_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (item_id) REFERENCES shop_items(id) ON DELETE CASCADE
        );
        """
    )
    count = db.execute("SELECT COUNT(*) AS c FROM shop_items").fetchone()["c"]
    if count == 0:
        db.executemany(
            """
            INSERT INTO shop_items (item_key, name, description, item_type, price, icon)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            SHOP_ITEMS,
        )
    db.commit()


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


@app.context_processor
def inject_helpers():
    return {
        "csrf_token": csrf_token(),
        "level_threshold": level_threshold,
        "level_progress": level_progress,
        "category_map": CATEGORY_MAP,
    }


def require_csrf():
    expected = session.get("csrf_token")
    supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        abort(400, description="Invalid request token.")


@app.before_request
def load_user_and_protect():
    g.user = None
    user_id = session.get("user_id")
    if user_id:
        g.user = get_db().execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if request.method == "POST" and request.endpoint not in {"login", "signup", "static"}:
        require_csrf()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def level_threshold(level: int) -> int:
    if level <= 1:
        return 0
    return int(100 * ((level - 1) ** 1.55))


def level_progress(xp: int, level: int):
    current_floor = level_threshold(level)
    next_floor = level_threshold(level + 1)
    needed = max(1, next_floor - current_floor)
    current = max(0, xp - current_floor)
    pct = min(100, round(current / needed * 100))
    return current, needed, pct


def calculate_level(xp: int) -> int:
    level = 1
    while xp >= level_threshold(level + 1):
        level += 1
    return level


def update_level_and_streak(user_id: int, old_xp: int, gained_xp: int):
    db = get_db()
    today = date.today()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    last = datetime.fromisoformat(user["last_activity"]).date() if user["last_activity"] else None

    if last == today:
        new_streak = user["streak"]
    elif last == today - timedelta(days=1):
        new_streak = user["streak"] + 1
    else:
        new_streak = 1

    new_xp = user["xp"] + gained_xp
    new_level = calculate_level(new_xp)
    db.execute(
        "UPDATE users SET xp = ?, level = ?, streak = ?, last_activity = ? WHERE id = ?",
        (new_xp, new_level, new_streak, today.isoformat(), user_id),
    )
    return new_level, new_streak, new_xp


def user_attributes(user_id):
    return get_db().execute(
        "SELECT * FROM attributes WHERE user_id = ?", (user_id,)
    ).fetchone()


def public_user(user_row):
    return {
        "id": user_row["id"],
        "name": user_row["name"],
        "xp": user_row["xp"],
        "level": user_row["level"],
        "gold": user_row["gold"],
        "streak": user_row["streak"],
    }


@app.route("/")
def index():
    if g.user:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        require_csrf()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        errors = []
        if len(name) < 2:
            errors.append("Name must be at least 2 characters.")
        if "@" not in email or "." not in email.split("@")[-1]:
            errors.append("Enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("signup.html")

        db = get_db()
        try:
            cur = db.execute(
                "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (name, email, generate_password_hash(password), datetime.utcnow().isoformat()),
            )
            user_id = cur.lastrowid
            db.execute("INSERT INTO attributes (user_id) VALUES (?)", (user_id,))
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            flash("An account with that email already exists.", "danger")
            return render_template("signup.html")

        session.clear()
        session["user_id"] = user_id
        csrf_token()
        flash("Character created. Your first adventure begins now!", "success")
        return redirect(url_for("dashboard"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        require_csrf()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")
        session.clear()
        session["user_id"] = user["id"]
        csrf_token()
        flash("Welcome back, hero!", "success")
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have been logged out safely.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    quests = db.execute(
        "SELECT * FROM quests WHERE user_id = ? ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, created_at DESC LIMIT 8",
        (g.user["id"],),
    ).fetchall()
    attrs = user_attributes(g.user["id"])
    activity = db.execute(
        "SELECT activity_date, SUM(xp_earned) xp, SUM(gold_earned) gold FROM activity_logs WHERE user_id = ? GROUP BY activity_date ORDER BY activity_date DESC LIMIT 7",
        (g.user["id"],),
    ).fetchall()
    current, needed, pct = level_progress(g.user["xp"], g.user["level"])
    return render_template(
        "dashboard.html",
        user=g.user,
        attrs=attrs,
        quests=quests,
        activity=activity,
        xp_current=current,
        xp_needed=needed,
        xp_pct=pct,
    )


@app.route("/quests")
@login_required
def quests():
    db = get_db()
    quests = db.execute(
        "SELECT * FROM quests WHERE user_id = ? ORDER BY created_at DESC", (g.user["id"],)
    ).fetchall()
    return render_template("quests.html", quests=quests)


@app.route("/quests/create", methods=["POST"])
@login_required
def create_quest():
    require_csrf()
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "other")
    difficulty = request.form.get("difficulty", "easy")
    if not title:
        flash("Quest title cannot be empty.", "danger")
        return redirect(url_for("quests"))
    if category not in CATEGORY_MAP:
        category = "other"
    if difficulty not in DIFFICULTY_REWARDS:
        difficulty = "easy"
    reward = DIFFICULTY_REWARDS[difficulty]
    db = get_db()
    db.execute(
        """
        INSERT INTO quests (user_id, title, description, category, difficulty, xp_reward, gold_reward, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (g.user["id"], title, description[:500], category, difficulty, reward["xp"], reward["gold"], datetime.utcnow().isoformat()),
    )
    db.commit()
    flash("Quest added to your mission board.", "success")
    return redirect(url_for("quests"))


@app.route("/quests/<int:quest_id>/complete", methods=["POST"])
@login_required
def complete_quest(quest_id):
    require_csrf()
    db = get_db()
    quest = db.execute(
        "SELECT * FROM quests WHERE id = ? AND user_id = ?", (quest_id, g.user["id"])
    ).fetchone()
    if not quest:
        abort(404)
    if quest["status"] == "completed":
        flash("That quest is already complete.", "warning")
        return redirect(url_for("quests"))

    db.execute(
        "UPDATE quests SET status = 'completed', completed_at = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), quest_id),
    )

    new_level, new_streak, new_xp = update_level_and_streak(
        g.user["id"], g.user["xp"], quest["xp_reward"]
    )

    attr_column = {
        "coding": "intellect",
        "study": "knowledge",
        "fitness": "strength",
        "mindfulness": "focus",
        "reading": "wisdom",
        "other": "discipline",
    }[quest["category"]]
    db.execute(
        f"UPDATE attributes SET {attr_column} = {attr_column} + ? WHERE user_id = ?",
        (max(1, quest["xp_reward"] // 30), g.user["id"]),
    )
    db.execute(
        "UPDATE users SET gold = gold + ? WHERE id = ?",
        (quest["gold_reward"], g.user["id"]),
    )
    db.execute(
        """
        INSERT INTO activity_logs (user_id, quest_id, activity_date, xp_earned, gold_earned, category)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (g.user["id"], quest_id, date.today().isoformat(), quest["xp_reward"], quest["gold_reward"], quest["category"]),
    )
    db.commit()

    previous_level = g.user["level"]
    payload = {
        "ok": True,
        "xp_gained": quest["xp_reward"],
        "gold_gained": quest["gold_reward"],
        "new_level": new_level,
        "level_up": new_level > previous_level,
        "streak": new_streak,
        "new_xp": new_xp,
    }
    if request.headers.get("Accept", "").startswith("application/json"):
        return jsonify(payload)
    if new_level > previous_level:
        flash(f"LEVEL UP! You reached level {new_level}.", "success")
    else:
        flash(f"Quest complete! +{quest['xp_reward']} XP and +{quest['gold_reward']} Gold.", "success")
    return redirect(url_for("quests"))


@app.route("/quests/<int:quest_id>/edit", methods=["GET", "POST"])
@login_required
def edit_quest(quest_id):
    db = get_db()
    quest = db.execute(
        "SELECT * FROM quests WHERE id = ? AND user_id = ?", (quest_id, g.user["id"])
    ).fetchone()
    if not quest:
        abort(404)
    if quest["status"] == "completed":
        flash("Completed quests are locked to preserve the activity record.", "warning")
        return redirect(url_for("quests"))
    if request.method == "POST":
        require_csrf()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "other")
        difficulty = request.form.get("difficulty", "easy")
        if not title:
            flash("Quest title cannot be empty.", "danger")
            return render_template("edit_quest.html", quest=quest)
        if category not in CATEGORY_MAP:
            category = "other"
        if difficulty not in DIFFICULTY_REWARDS:
            difficulty = "easy"
        reward = DIFFICULTY_REWARDS[difficulty]
        db.execute(
            """
            UPDATE quests
            SET title = ?, description = ?, category = ?, difficulty = ?, xp_reward = ?, gold_reward = ?
            WHERE id = ? AND user_id = ?
            """,
            (title, description[:500], category, difficulty, reward["xp"], reward["gold"], quest_id, g.user["id"]),
        )
        db.commit()
        flash("Quest updated.", "success")
        return redirect(url_for("quests"))
    return render_template("edit_quest.html", quest=quest)


@app.route("/quests/<int:quest_id>/delete", methods=["POST"])
@login_required
def delete_quest(quest_id):
    require_csrf()
    db = get_db()
    quest = db.execute(
        "SELECT * FROM quests WHERE id = ? AND user_id = ?", (quest_id, g.user["id"])
    ).fetchone()
    if not quest:
        abort(404)
    db.execute("DELETE FROM quests WHERE id = ?", (quest_id,))
    db.commit()
    flash("Quest removed.", "success")
    return redirect(url_for("quests"))


@app.route("/character")
@login_required
def character():
    return render_template(
        "character.html",
        user=g.user,
        attrs=user_attributes(g.user["id"]),
        inventory=get_inventory(g.user["id"]),
    )


def get_inventory(user_id):
    return get_db().execute(
        """
        SELECT s.* FROM inventory i
        JOIN shop_items s ON s.id = i.item_id
        WHERE i.user_id = ? ORDER BY i.purchased_at DESC
        """,
        (user_id,),
    ).fetchall()


@app.route("/shop")
@login_required
def shop():
    db = get_db()
    items = db.execute("SELECT * FROM shop_items ORDER BY price ASC").fetchall()
    owned = {
        row["item_id"]
        for row in db.execute(
            "SELECT item_id FROM inventory WHERE user_id = ?", (g.user["id"],)
        ).fetchall()
    }
    return render_template("shop.html", items=items, owned=owned, user=g.user)


@app.route("/shop/<int:item_id>/buy", methods=["POST"])
@login_required
def buy_item(item_id):
    require_csrf()
    db = get_db()
    item = db.execute("SELECT * FROM shop_items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        abort(404)
    exists = db.execute(
        "SELECT 1 FROM inventory WHERE user_id = ? AND item_id = ?", (g.user["id"], item_id)
    ).fetchone()
    if exists:
        flash("You already own this item.", "warning")
        return redirect(url_for("shop"))
    if g.user["gold"] < item["price"]:
        flash("Not enough Gold for this purchase.", "danger")
        return redirect(url_for("shop"))
    db.execute("UPDATE users SET gold = gold - ? WHERE id = ?", (item["price"], g.user["id"]))
    db.execute(
        "INSERT INTO inventory (user_id, item_id, purchased_at) VALUES (?, ?, ?)",
        (g.user["id"], item_id, datetime.utcnow().isoformat()),
    )
    db.commit()
    flash(f"Unlocked {item['name']}.", "success")
    return redirect(url_for("shop"))


@app.route("/history")
@login_required
def history():
    db = get_db()
    logs = db.execute(
        """
        SELECT l.*, q.title FROM activity_logs l
        LEFT JOIN quests q ON q.id = l.quest_id
        WHERE l.user_id = ?
        ORDER BY l.activity_date DESC, l.id DESC
        LIMIT 100
        """,
        (g.user["id"],),
    ).fetchall()
    return render_template("history.html", logs=logs)


@app.route("/about")
def about():
    return render_template("about.html")


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", code=400, message=str(error.description or "Bad request.")), 400


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="The route or quest you requested was not found."), 404


@app.errorhandler(500)
def server_error(_error):
    return render_template("error.html", code=500, message="The server encountered an error. Please try again."), 500


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)

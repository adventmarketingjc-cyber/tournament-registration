import os
import sqlite3
import random
from datetime import datetime, timedelta, timezone
from flask import Flask, g, request, redirect, url_for, render_template_string, abort

DATABASE = os.environ.get("DATABASE", "tournament.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(UTC)


def fmt_dt(dt_iso: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_iso)
    except Exception:
        return dt_iso
    return dt.strftime("%b %d, %Y %I:%M %p UTC")


# -----------------------
# Database helpers
# -----------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript("""
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS tournaments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        registration_deadline_utc TEXT NOT NULL,
        created_at_utc TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        gamertag TEXT NOT NULL,
        availability_days TEXT NOT NULL DEFAULT '',
        availability_window TEXT NOT NULL DEFAULT '',
        availability_notes TEXT NOT NULL DEFAULT '',
        created_at_utc TEXT NOT NULL,
        UNIQUE(tournament_id, gamertag),
        FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS tournament_meta (
        tournament_id INTEGER PRIMARY KEY,
        generated_at_utc TEXT,
        rounds INTEGER NOT NULL DEFAULT 5,
        game_types TEXT NOT NULL DEFAULT 'Type A,Type B,Type C',
        FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        round_num INTEGER NOT NULL,
        game_type TEXT NOT NULL,
        team_a TEXT NOT NULL,
        team_b TEXT NOT NULL,
        winner TEXT,
        created_at_utc TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
    );
    """)
    db.commit()


@app.before_request
def _startup():
    init_db()


# -----------------------
# Retro Space Invaders theme (CSS only)
# -----------------------
BASE_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }}</title>

  <style>
    :root{
      --bg: #05060a;
      --panel: rgba(10, 18, 26, 0.78);
      --panel-border: rgba(0, 255, 153, 0.35);
      --text: #d7ffe7;
      --muted: rgba(215, 255, 231, 0.72);
      --accent: #00ff99;
      --accent2: #7cffd5;
      --danger: #ff5c7a;
      --warn: #ffd166;
      --shadow: rgba(0, 255, 153, 0.18);
    }

    body{
      margin: 0;
      color: var(--text);
      background: radial-gradient(1200px 800px at 50% -10%, rgba(0,255,153,0.10), transparent 55%),
                  radial-gradient(900px 600px at 20% 10%, rgba(124,255,213,0.08), transparent 60%),
                  radial-gradient(1000px 700px at 80% 30%, rgba(255,255,255,0.04), transparent 60%),
                  var(--bg);
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      letter-spacing: 0.2px;
    }

    body::before{
      content:"";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        radial-gradient(1px 1px at 10% 20%, rgba(255,255,255,0.35) 50%, transparent 55%),
        radial-gradient(1px 1px at 30% 80%, rgba(255,255,255,0.25) 50%, transparent 55%),
        radial-gradient(1px 1px at 70% 30%, rgba(255,255,255,0.30) 50%, transparent 55%),
        radial-gradient(1px 1px at 90% 60%, rgba(255,255,255,0.22) 50%, transparent 55%),
        radial-gradient(1px 1px at 50% 50%, rgba(255,255,255,0.18) 50%, transparent 55%);
      opacity: 0.8;
      filter: blur(0.2px);
      animation: drift 10s linear infinite;
    }

    @keyframes drift{
      0% { transform: translateY(0); }
      100% { transform: translateY(10px); }
    }

    body::after{
      content:"";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background:
        linear-gradient(to bottom,
          rgba(255,255,255,0.03),
          rgba(255,255,255,0.00) 3px,
          rgba(0,0,0,0.06) 4px);
      background-size: 100% 6px;
      mix-blend-mode: overlay;
      opacity: 0.22;
      animation: flicker 3.5s infinite;
    }

    @keyframes flicker{
      0%, 100% { opacity: 0.20; }
      40% { opacity: 0.25; }
      55% { opacity: 0.18; }
      70% { opacity: 0.24; }
    }

    .wrap{
      max-width: 920px;
      margin: 44px auto;
      padding: 0 16px 50px 16px;
      position: relative;
    }

    h1{
      margin: 0 0 10px 0;
      font-size: 26px;
      text-transform: uppercase;
      letter-spacing: 2px;
      color: var(--accent);
      text-shadow: 0 0 18px var(--shadow);
    }

    .subtitle{
      margin: 0 0 16px 0;
      color: var(--muted);
      line-height: 1.4;
    }

    .card{
      border: 1px solid var(--panel-border);
      background: var(--panel);
      border-radius: 14px;
      padding: 18px;
      box-shadow: 0 0 0 2px rgba(0,255,153,0.07), 0 12px 40px rgba(0,0,0,0.55);
      position: relative;
      overflow: hidden;
    }

    .card::before{
      content:"";
      position:absolute;
      inset: 0;
      background: radial-gradient(600px 240px at 50% 0%, rgba(0,255,153,0.10), transparent 60%);
      pointer-events:none;
    }

    label{
      display:block;
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-top: 10px;
    }

    input, select{
      width: 100%;
      padding: 12px;
      margin: 8px 0 10px 0;
      box-sizing: border-box;
      border-radius: 10px;
      border: 1px solid rgba(0,255,153,0.35);
      background: rgba(0,0,0,0.35);
      color: var(--text);
      outline: none;
      box-shadow: inset 0 0 0 1px rgba(0,255,153,0.10);
    }

    input:focus, select:focus{
      border-color: rgba(124,255,213,0.8);
      box-shadow: 0 0 0 3px rgba(0,255,153,0.18);
    }

    button{
      margin-top: 10px;
      padding: 12px 16px;
      border-radius: 12px;
      border: 1px solid rgba(0,255,153,0.55);
      background: linear-gradient(180deg, rgba(0,255,153,0.18), rgba(0,255,153,0.06));
      color: var(--accent);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1px;
      cursor: pointer;
      box-shadow: 0 0 18px rgba(0,255,153,0.12);
    }

    button:hover{
      border-color: rgba(124,255,213,0.85);
      box-shadow: 0 0 22px rgba(124,255,213,0.18);
      transform: translateY(-1px);
    }

    button:active{
      transform: translateY(0px);
      box-shadow: 0 0 12px rgba(124,255,213,0.12);
    }

    .muted{ color: var(--muted); font-size: 13px; }
    ul{ padding-left: 18px; }

    code{
      background: rgba(0,0,0,0.35);
      border: 1px solid rgba(0,255,153,0.25);
      padding: 2px 6px;
      border-radius: 8px;
      color: var(--accent2);
      word-break: break-all;
    }

    .hr{
      height: 1px;
      background: rgba(0,255,153,0.18);
      margin: 16px 0;
    }

    .success{
      background: rgba(0,255,153,0.08);
      border: 1px solid rgba(0,255,153,0.35);
      padding: 10px;
      border-radius: 10px;
    }

    .warning{
      background: rgba(255,209,102,0.08);
      border: 1px solid rgba(255,209,102,0.35);
      padding: 10px;
      border-radius: 10px;
      color: rgba(255,245,220,0.92);
    }

    .closed{
      background: rgba(255,92,122,0.08);
      border: 1px solid rgba(255,92,122,0.35);
      padding: 10px;
      border-radius: 10px;
      color: rgba(255,230,236,0.92);
    }

    .grid{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }
    @media (max-width: 720px) { .grid { grid-template-columns: 1fr; } }

    .days-box{
      border: 1px solid rgba(0,255,153,0.22);
      border-radius: 12px;
      padding: 10px;
      background: rgba(0,0,0,0.20);
    }

    .day{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin: 6px 10px 6px 0;
      font-size: 13px;
      color: rgba(215,255,231,0.90);
    }

    a{ color: var(--accent2); }
  </style>
</head>

<body>
  <div class="wrap">
    <h1>{{ title }}</h1>
    <p class="subtitle">{{ subtitle }}</p>
    <div class="card">
      {{ body|safe }}
    </div>
  </div>
</body>
</html>
"""


def render_page(title, subtitle, body):
    return render_template_string(BASE_HTML, title=title, subtitle=subtitle, body=body)


def registration_open(tournament_row) -> bool:
    deadline = datetime.fromisoformat(tournament_row["registration_deadline_utc"])
    return utc_now() <= deadline


# -----------------------
# Registration routes
# -----------------------
@app.get("/")
def home():
    return render_page(
        "Registration Link Builder",
        "Create a tournament signup link that automatically closes after 24 hours.",
        f"""
        <form method="post" action="{url_for('create_tournament')}">
          <label>Tournament Name</label>
          <input name="name" placeholder="Example: 3v3 Tryouts" required>

          <label>Tournament Code (used in the join link)</label>
          <input name="code" placeholder="Example: TRYOUTS2026" required>

          <button type="submit">Create 24-Hour Registration Link</button>
        </form>
        """
    )


@app.post("/tournaments")
def create_tournament():
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper()

    if not name or not code:
        abort(400, "Name and code required.")

    created = utc_now()
    deadline = created + timedelta(hours=24)

    db = get_db()
    try:
        db.execute(
            "INSERT INTO tournaments (name, code, registration_deadline_utc, created_at_utc) VALUES (?, ?, ?, ?)",
            (name, code, deadline.isoformat(), created.isoformat()),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return render_page("Error", "", "<p>That tournament code already exists. Please pick a different code.</p>")

    return redirect(url_for("admin_tournament", code=code))


@app.get("/join/<code>")
def join_page(code):
    db = get_db()
    t = db.execute("SELECT * FROM tournaments WHERE code = ?", (code.upper(),)).fetchone()
    if not t:
        abort(404)

    open_now = registration_open(t)

    players = db.execute(
        """
        SELECT gamertag, availability_days, availability_window, availability_notes
        FROM players
        WHERE tournament_id = ?
        ORDER BY created_at_utc DESC
        """,
        (t["id"],),
    ).fetchall()

    player_list = ""
    if players:
        for p in players:
            extras = f"{p['availability_days']} | {p['availability_window']} ET"
            if p["availability_notes"]:
                extras += f" | {p['availability_notes']}"
            player_list += f"<li><b>{p['gamertag']}</b> <span class='muted'>({extras})</span></li>"
    else:
        player_list = "<li>No players yet</li>"

    deadline_text = fmt_dt(t["registration_deadline_utc"])

    if not open_now:
        return render_page(
            f"Join: {t['name']}",
            "Registration is closed.",
            f"""
            <div class="closed">
              <b>Registration closed.</b><br>
              Deadline was: <code>{deadline_text}</code>
            </div>

            <div class="hr"></div>

            <h3>Registered Players ({len(players)})</h3>
            <ul>{player_list}</ul>
            """,
        )

    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_checks = "".join(
        [f'<label class="day"><input type="checkbox" name="days" value="{d}"> {d}</label>' for d in days]
    )

    time_windows = ["6pm-8pm", "7pm-9pm", "8pm-10pm", "8pm-11pm", "9pm-11pm"]
    time_options = "".join([f'<option value="{tw}">{tw} ET</option>' for tw in time_windows])

    return render_page(
        f"Join: {t['name']}",
        "Enter your gamertag and availability to register.",
        f"""
        <div class="warning">
          <b>Registration is open for 24 hours only.</b><br>
          Closes at: <code>{deadline_text}</code>
        </div>

        <div class="hr"></div>

        <form method="post" action="{url_for('join_submit', code=code)}">
          <label>Gamertag</label>
          <input name="gamertag" placeholder="Example: PlayerOne" required>

          <div class="grid">
            <div>
              <label>Days Available (ET)</label>
              <div class="days-box">
                {day_checks}
              </div>
              <p class="muted" style="margin-top:8px;">Pick all that apply.</p>
            </div>

            <div>
              <label>Time Window (ET)</label>
              <select name="time_window" required>
                <option value="">-- select --</option>
                {time_options}
              </select>

              <label>Notes (optional)</label>
              <input name="notes" placeholder="Example: Every other Wednesday">
            </div>
          </div>

          <button type="submit">Join Tournament</button>
        </form>

        <div class="hr"></div>

        <h3>Registered Players ({len(players)})</h3>
        <ul>{player_list}</ul>
        """,
    )


@app.post("/join/<code>")
def join_submit(code):
    gamertag = request.form.get("gamertag", "").strip()
    days = request.form.getlist("days")
    time_window = request.form.get("time_window", "").strip()
    notes = request.form.get("notes", "").strip()

    if not gamertag:
        abort(400, "Gamertag is required.")
    if not days:
        abort(400, "Please select at least one day.")
    if not time_window:
        abort(400, "Please select a time window.")

    db = get_db()
    t = db.execute("SELECT * FROM tournaments WHERE code = ?", (code.upper(),)).fetchone()
    if not t:
        abort(404)

    if not registration_open(t):
        return render_page("Registration Closed", "", "<p class='closed'><b>Registration is closed.</b></p>")

    availability_days = ",".join(days)

    try:
        db.execute(
            """
            INSERT INTO players
              (tournament_id, gamertag, availability_days, availability_window, availability_notes, created_at_utc)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (t["id"], gamertag, availability_days, time_window, notes, utc_now().isoformat()),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return render_page(
            "Already Registered",
            "",
            f"""
            <p class="success"><b>{gamertag}</b> is already registered.</p>
            <p><a href="{url_for('join_page', code=code)}">Back</a></p>
            """,
        )

    return redirect(url_for("join_page", code=code))


# -----------------------
# Tournament generation + viewing
# -----------------------
def split_teams(players6):
    team_a = players6[:3]
    team_b = players6[3:]
    return team_a, team_b


@app.post("/admin/<code>/generate")
def generate_tournament(code):
    db = get_db()
    t = db.execute("SELECT * FROM tournaments WHERE code = ?", (code.upper(),)).fetchone()
    if not t:
        abort(404)

    players = db.execute(
        "SELECT gamertag FROM players WHERE tournament_id = ? ORDER BY created_at_utc ASC",
        (t["id"],)
    ).fetchall()
    gamertags = [p["gamertag"] for p in players]

    if len(gamertags) < 6:
        return render_page(
            f"Admin: {t['name']}",
            "Not enough players yet.",
            f"""
            <p class="closed"><b>Need at least 6 players</b> to generate a 3v3 tournament. Currently: {len(gamertags)}</p>
            <p><a href="{url_for('admin_tournament', code=code)}">Back</a></p>
            """,
        )

    meta = db.execute("SELECT * FROM tournament_meta WHERE tournament_id = ?", (t["id"],)).fetchone()
    if meta and meta["generated_at_utc"]:
        return redirect(url_for("tournament_view", code=code.upper()))

    if not meta:
        db.execute("INSERT INTO tournament_meta (tournament_id) VALUES (?)", (t["id"],))
        db.commit()

    meta = db.execute("SELECT * FROM tournament_meta WHERE tournament_id = ?", (t["id"],)).fetchone()
    rounds = int(meta["rounds"])
    game_types = [x.strip() for x in meta["game_types"].split(",") if x.strip()]
    if not game_types:
        game_types = ["Type A", "Type B", "Type C"]

    db.execute("DELETE FROM matches WHERE tournament_id = ?", (t["id"],))
    db.commit()

    for r in range(1, rounds + 1):
        picked = gamertags[:]
        random.shuffle(picked)
        players6 = picked[:6]
        team_a, team_b = split_teams(players6)
        game_type = game_types[(r - 1) % len(game_types)]

        db.execute(
            """
            INSERT INTO matches (tournament_id, round_num, game_type, team_a, team_b, winner)
            VALUES (?, ?, ?, ?, ?, NULL)
            """,
            (t["id"], r, game_type, ",".join(team_a), ",".join(team_b))
        )

    db.execute(
        "UPDATE tournament_meta SET generated_at_utc = ? WHERE tournament_id = ?",
        (utc_now().isoformat(), t["id"])
    )
    db.commit()

    return redirect(url_for("tournament_view", code=code.upper()))


@app.get("/t/<code>")
def tournament_view(code):
    db = get_db()
    t = db.execute("SELECT * FROM tournaments WHERE code = ?", (code.upper(),)).fetchone()
    if not t:
        abort(404)

    meta = db.execute("SELECT * FROM tournament_meta WHERE tournament_id = ?", (t["id"],)).fetchone()
    if not meta or not meta["generated_at_utc"]:
        return render_page(
            f"Tournament: {t['name']}",
            "Tournament not generated yet.",
            f"<p><a href='{url_for('admin_tournament', code=code)}'>Go to Admin</a></p>"
        )

    matches = db.execute(
        "SELECT * FROM matches WHERE tournament_id = ? ORDER BY round_num ASC",
        (t["id"],)
    ).fetchall()

    def fmt_team(s):
        return " vs ".join([x.strip() for x in s.split(",")])

    rows = ""
    for m in matches:
        winner = m["winner"] or "—"
        rows += f"""
          <div>
            <b>Round {m['round_num']}</b> <span class="muted">({m['game_type']})</span><br>
            <span class="muted">Team A:</span> {fmt_team(m['team_a'])}<br>
            <span class="muted">Team B:</span> {fmt_team(m['team_b'])}<br>
            <span class="muted">Winner:</span> <b>{winner}</b>
            <form method="post" action="{url_for('set_winner', code=code, match_id=m['id'])}" style="margin-top:8px;">
              <select name="winner" required>
                <option value="">Set winner…</option>
                <option value="A">Team A</option>
                <option value="B">Team B</option>
              </select>
              <button type="submit">Save Winner</button>
            </form>
          </div>
          <div class="hr"></div>
        """

    return render_page(
        f"Tournament: {t['name']}",
        "Rounds generated. Record match winners below.",
        f"""
        <p><a href="{url_for('admin_tournament', code=code)}">Back to Admin</a></p>
        <div class="hr"></div>
        {rows}
        """
    )


@app.post("/t/<code>/match/<int:match_id>/winner")
def set_winner(code, match_id):
    winner = request.form.get("winner", "").strip().upper()
    if winner not in ("A", "B"):
        abort(400)

    db = get_db()
    t = db.execute("SELECT * FROM tournaments WHERE code = ?", (code.upper(),)).fetchone()
    if not t:
        abort(404)

    db.execute(
        "UPDATE matches SET winner = ? WHERE id = ? AND tournament_id = ?",
        (winner, match_id, t["id"])
    )
    db.commit()

    return redirect(url_for("tournament_view", code=code.upper()))


# -----------------------
# Admin
# -----------------------
@app.get("/admin/<code>")
def admin_tournament(code):
    db = get_db()
    t = db.execute("SELECT * FROM tournaments WHERE code = ?", (code.upper(),)).fetchone()
    if not t:
        abort(404)

    players = db.execute(
        """
        SELECT gamertag, availability_days, availability_window, availability_notes
        FROM players
        WHERE tournament_id = ?
        ORDER BY created_at_utc ASC
        """,
        (t["id"],),
    ).fetchall()

    join_link = url_for("join_page", code=code.upper(), _external=True)
    tournament_link = url_for("tournament_view", code=code.upper(), _external=True)
    deadline_text = fmt_dt(t["registration_deadline_utc"])
    open_now = registration_open(t)

    rows = ""
    if players:
        for p in players:
            extras = f"{p['availability_days']} | {p['availability_window']} ET"
            if p["availability_notes"]:
                extras += f" | {p['availability_notes']}"
            rows += f"<li><b>{p['gamertag']}</b> <span class='muted'>({extras})</span></li>"
    else:
        rows = "<li>No players yet</li>"

    meta = db.execute("SELECT * FROM tournament_meta WHERE tournament_id = ?", (t["id"],)).fetchone()
    generated = bool(meta and meta["generated_at_utc"])

    status_html = (
        f"<div class='warning'><b>Registration OPEN</b><br>Closes at: <code>{deadline_text}</code></div>"
        if open_now
        else f"<div class='closed'><b>Registration CLOSED</b><br>Closed at: <code>{deadline_text}</code></div>"
    )

    if generated:
        gen_block = f"""
        <div class="success">
          <b>Tournament generated.</b><br>
          Tournament page: <code>{tournament_link}</code>
        </div>
        """
    else:
        gen_block = f"""
        <form method="post" action="{url_for('generate_tournament', code=code)}">
          <button type="submit">Generate Tournament</button>
        </form>
        <p class="muted">Tournament page will appear here after generation.</p>
        """

    return render_page(
        f"Admin: {t['name']}",
        "Copy the join link and share it with players. Generate tournament when ready.",
        f"""
        {status_html}

        <div class="hr"></div>

        <p><b>Join Link:</b></p>
        <p><code>{join_link}</code></p>

        <div class="hr"></div>

        {gen_block}

        <div class="hr"></div>

        <h3>Registered Players ({len(players)})</h3>
        <ul>{rows}</ul>
        """
    )


if __name__ == "__main__":
    app.run(debug=True)

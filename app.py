import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = "student-portal-final-secret-key"


# =========================================================
# DATABASE
# =========================================================

DATABASE = "student.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # USERS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # SUBJECTS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)

    # GOALS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            completed INTEGER DEFAULT 0
        )
    """)

    # NOTES
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            content TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# LOGIN REQUIRED
# =========================================================

def login_required(route_function):

    @wraps(route_function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        return route_function(*args, **kwargs)

    return wrapper


# =========================================================
# HOME / DASHBOARD
# =========================================================

@app.route("/")
@login_required
def home():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM subjects")
    total_subjects = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM goals")
    total_goals = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM goals
        WHERE completed = 1
    """)
    completed_goals = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM notes")
    total_notes = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "index.html",
        total_subjects=total_subjects,
        total_goals=total_goals,
        completed_goals=completed_goals,
        total_notes=total_notes
    )


# =========================================================
# SIGNUP
# =========================================================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if "user_id" in session:
        return redirect(url_for("home"))

    error = ""

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password:
            error = "Please fill in all fields."

        elif password != confirm_password:
            error = "Passwords do not match."

        elif len(password) < 6:
            error = "Password must be at least 6 characters."

        else:

            conn = get_db()
            cursor = conn.cursor()

            try:

                hashed_password = generate_password_hash(password)

                cursor.execute("""
                    INSERT INTO users
                    (name, email, password)
                    VALUES (?, ?, ?)
                """, (
                    name,
                    email,
                    hashed_password
                ))

                conn.commit()

                user_id = cursor.lastrowid

                session["user_id"] = user_id
                session["user_name"] = name

                conn.close()

                return redirect(url_for("home"))

            except sqlite3.IntegrityError:

                conn.close()

                error = "This email is already registered."

    return render_template(
        "signup.html",
        error=error
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if "user_id" in session:
        return redirect(url_for("home"))

    error = ""

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM users
            WHERE email = ?
        """, (email,))

        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect(url_for("home"))

        error = "Invalid email or password."

    return render_template(
        "login.html",
        error=error
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# SUBJECTS
# =========================================================

@app.route("/subjects", methods=["GET", "POST"])
@login_required
def subjects():

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        if name:

            cursor.execute("""
                INSERT INTO subjects (name)
                VALUES (?)
            """, (name,))

            conn.commit()

    cursor.execute("""
        SELECT *
        FROM subjects
        ORDER BY id DESC
    """)

    subjects_list = cursor.fetchall()

    conn.close()

    return render_template(
        "subjects.html",
        subjects=subjects_list
    )


# =========================================================
# SUBJECT DETAIL
# =========================================================

@app.route(
    "/subject/<int:subject_id>",
    methods=["GET", "POST"]
)
@login_required
def subject_detail(subject_id):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM subjects
        WHERE id = ?
    """, (subject_id,))

    subject = cursor.fetchone()

    if subject is None:

        conn.close()

        return "Subject not found", 404

    # ADD NOTE
    if request.method == "POST":

        content = request.form.get(
            "content",
            ""
        ).strip()

        if content:

            cursor.execute("""
                INSERT INTO notes
                (subject_id, content)
                VALUES (?, ?)
            """, (
                subject_id,
                content
            ))

            conn.commit()

    # GET NOTES
    cursor.execute("""
        SELECT *
        FROM notes
        WHERE subject_id = ?
        ORDER BY id DESC
    """, (subject_id,))

    notes = cursor.fetchall()

    conn.close()

    return render_template(
        "subject_detail.html",
        subject=subject,
        notes=notes
    )


# =========================================================
# EDIT SUBJECT
# =========================================================

@app.route(
    "/edit_subject/<int:subject_id>",
    methods=["GET", "POST"]
)
@login_required
def edit_subject(subject_id):

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        if name:

            cursor.execute("""
                UPDATE subjects
                SET name = ?
                WHERE id = ?
            """, (
                name,
                subject_id
            ))

            conn.commit()
            conn.close()

            return redirect(url_for("subjects"))

    cursor.execute("""
        SELECT *
        FROM subjects
        WHERE id = ?
    """, (subject_id,))

    subject = cursor.fetchone()

    conn.close()

    if subject is None:
        return "Subject not found", 404

    return render_template(
        "edit_subject.html",
        subject=subject
    )


# =========================================================
# DELETE SUBJECT
# =========================================================

@app.route("/delete_subject/<int:subject_id>")
@login_required
def delete_subject(subject_id):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM notes
        WHERE subject_id = ?
    """, (subject_id,))

    cursor.execute("""
        DELETE FROM subjects
        WHERE id = ?
    """, (subject_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("subjects"))


# =========================================================
# DELETE NOTE
# =========================================================

@app.route(
    "/delete_note/<int:note_id>/<int:subject_id>"
)
@login_required
def delete_note(note_id, subject_id):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM notes
        WHERE id = ?
    """, (note_id,))

    conn.commit()
    conn.close()

    return redirect(
        url_for(
            "subject_detail",
            subject_id=subject_id
        )
    )


# =========================================================
# EDIT NOTE
# =========================================================

@app.route(
    "/edit_note/<int:note_id>/<int:subject_id>",
    methods=["GET", "POST"]
)
@login_required
def edit_note(note_id, subject_id):

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":

        content = request.form.get(
            "content",
            ""
        ).strip()

        if content:

            cursor.execute("""
                UPDATE notes
                SET content = ?
                WHERE id = ?
            """, (
                content,
                note_id
            ))

            conn.commit()
            conn.close()

            return redirect(
                url_for(
                    "subject_detail",
                    subject_id=subject_id
                )
            )

    cursor.execute("""
        SELECT *
        FROM notes
        WHERE id = ?
    """, (note_id,))

    note = cursor.fetchone()

    conn.close()

    if note is None:
        return "Note not found", 404

    return render_template(
        "edit_note.html",
        note=note,
        subject_id=subject_id
    )


# =========================================================
# GOALS
# =========================================================

@app.route("/goals", methods=["GET", "POST"])
@login_required
def goals():

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        if title:

            cursor.execute("""
                INSERT INTO goals
                (title, completed)
                VALUES (?, ?)
            """, (
                title,
                0
            ))

            conn.commit()

    cursor.execute("""
        SELECT *
        FROM goals
        ORDER BY id DESC
    """)

    goals_list = cursor.fetchall()

    conn.close()

    return render_template(
        "goals.html",
        goals=goals_list
    )


# =========================================================
# COMPLETE GOAL
# =========================================================

@app.route("/complete_goal/<int:goal_id>")
@login_required
def complete_goal(goal_id):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE goals
        SET completed = 1
        WHERE id = ?
    """, (goal_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("goals"))


# =========================================================
# EDIT GOAL
# =========================================================

@app.route(
    "/edit_goal/<int:goal_id>",
    methods=["GET", "POST"]
)
@login_required
def edit_goal(goal_id):

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        if title:

            cursor.execute("""
                UPDATE goals
                SET title = ?
                WHERE id = ?
            """, (
                title,
                goal_id
            ))

            conn.commit()
            conn.close()

            return redirect(url_for("goals"))

    cursor.execute("""
        SELECT *
        FROM goals
        WHERE id = ?
    """, (goal_id,))

    goal = cursor.fetchone()

    conn.close()

    if goal is None:
        return "Goal not found", 404

    return render_template(
        "edit_goal.html",
        goal=goal
    )


# =========================================================
# DELETE GOAL
# =========================================================

@app.route("/delete_goal/<int:goal_id>")
@login_required
def delete_goal(goal_id):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM goals
        WHERE id = ?
    """, (goal_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("goals"))


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    init_db()

    app.run(
        debug=True
    )
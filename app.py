from flask import Flask, request, redirect, render_template, url_for
import sqlite3
import string
import random
import os
import re
import sys

app = Flask(__name__)

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

DB_FILE = resource_path("shortener.db")

# Initialize DB
def init_db():
    if not os.path.exists(DB_FILE):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute('''
                CREATE TABLE urls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_url TEXT NOT NULL,
                    short_code TEXT NOT NULL UNIQUE
                )
            ''')
        print("✅ Database initialized.")

def generate_code(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def slugify_url(url, style="caps", max_len=16):
    url = re.sub(r"https?://", "", url)
    parts = re.split(r'[\/\-\._\?#]+', url)

    blacklist = {
        'www', 'com', 'org', 'net', 'html', 'php', 'learn', 'lecture', 'start', 
        'overview', 'course', 'watch', 'home', 'index', 'default', 'login'
    }

    keywords = [re.sub(r'\W+', '', part) for part in parts if part]
    keywords = [kw for kw in keywords if kw.lower() not in blacklist and len(kw) > 1]

    # Sort by length and uniqueness, prioritize alphanum and useful patterns
    scored = sorted(keywords, key=lambda k: (-len(k), k.isalpha(), k.lower()))

    slug_parts = []
    total_len = 0

    for kw in scored:
        word = kw.lower()
        word_formatted = word.capitalize() if style == "caps" else word
        next_len = len(word_formatted) + (1 if slug_parts and style == "dash" else 0)
        if total_len + next_len <= max_len:
            slug_parts.append(word_formatted)
            total_len += next_len
        if total_len >= max_len:
            break

    if style == "caps":
        return ''.join(slug_parts)
    else:
        return '-'.join(slug_parts)

@app.route("/", methods=["GET", "POST"])
def index():
    short_url = None
    error_msg = None

    if request.method == "POST":
        if "clear" in request.form:
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute("DELETE FROM urls")
            return redirect(url_for("index"))

        original_url = request.form["url"].strip()
        custom_code = request.form["code"].strip()
        style = request.form.get("style", "caps")

        if custom_code:
            short_code = custom_code
        else:
            short_code = slugify_url(original_url, style=style)
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.execute("SELECT 1 FROM urls WHERE short_code = ?", (short_code,))
                if cursor.fetchone():
                    short_code = generate_code()

        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute("SELECT 1 FROM urls WHERE short_code = ?", (short_code,))
            if cursor.fetchone():
                error_msg = f"\u274c Short code '{short_code}' already exists. Try another."
            else:
                conn.execute("INSERT INTO urls (original_url, short_code) VALUES (?, ?)", (original_url, short_code))
                short_url = request.host_url + short_code

    with sqlite3.connect(DB_FILE) as conn:
        history = conn.execute("SELECT original_url, short_code FROM urls ORDER BY id DESC LIMIT 10").fetchall()

    return render_template("index.html", short_url=short_url, error=error_msg, history=history)

@app.route("/<code>")
def redirect_to_url(code):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute("SELECT original_url FROM urls WHERE short_code = ?", (code,))
        row = cursor.fetchone()
    if row:
        return redirect(row[0])
    else:
        return "<h3>URL not found</h3>", 404

if __name__ == "__main__":
    init_db()
    app.run(debug=True)

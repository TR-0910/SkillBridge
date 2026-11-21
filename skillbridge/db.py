"""SQLite helpers: schema, connections, and job loading."""
import json
import sqlite3
from contextlib import closing

from flask import g

import config
from job_sources import dedupe

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  education TEXT DEFAULT '',
  interests TEXT DEFAULT '',
  projects TEXT DEFAULT '',
  certificates TEXT DEFAULT '',
  resume_text TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS user_skills (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  skill TEXT NOT NULL,
  level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 3),
  PRIMARY KEY (user_id, skill)
);
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  company TEXT NOT NULL,
  location TEXT NOT NULL,
  description TEXT NOT NULL,
  apply_url TEXT DEFAULT '',
  source TEXT DEFAULT '',
  skills TEXT NOT NULL,            -- JSON list extracted from the description
  UNIQUE (title, company, location)
);
CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  notes TEXT DEFAULT '',
  updated_at TEXT NOT NULL,
  UNIQUE (user_id, job_id)
);
"""


def connect():
    conn = sqlite3.connect(config.DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    with closing(connect()) as conn:
        conn.executescript(SCHEMA)


def load_jobs(source, skill_dict):
    """Insert new jobs from a source (duplicates skipped). Returns how many were added."""
    added = 0
    with closing(connect()) as conn, conn:
        for j in dedupe(source.fetch()):
            skills = sorted(skill_dict.extract(f"{j['title']} {j['description']}"))
            cur = conn.execute(
                "INSERT OR IGNORE INTO jobs (title, company, location, description, apply_url, source, skills)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (j["title"], j["company"], j["location"], j["description"],
                 j.get("apply_url", ""), j.get("source", ""), json.dumps(skills)),
            )
            added += cur.rowcount
    return added


def all_jobs():
    with closing(connect()) as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY id").fetchall()
    return [{**dict(r), "skills": json.loads(r["skills"])} for r in rows]

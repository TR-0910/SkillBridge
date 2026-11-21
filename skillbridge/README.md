# SkillBridge: Data-Driven Career Guidance and Upskilling System

Flask + SQLite + Bootstrap web app. Students build a profile, see ranked job matches with a
match percentage, find missing skills, get course links, and track applications.

## Run it

```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                                         # open http://127.0.0.1:5000
```

The database (`career.db`) is created on first run and seeded from `data/jobs.csv`.
Set `SECRET_KEY` in your environment before sharing the app with anyone.

## How it maps to your methodology slide

| Methodology step | Where it lives |
|---|---|
| Data collection, cleaning, duplicates removed | `job_sources.py` (`CSVJobSource`, `dedupe`), `db.load_jobs` |
| Skill extraction from jobs and resume | `skills.py`, dictionary in `data/skills.csv` |
| Student profile (education, skill levels, projects, certificates) | `/profile` route, `profile.html` |
| TF-IDF + cosine similarity ranking | `recommender.Recommender.rank` |
| Match score: matched / partial / missing | `recommender.Recommender.analyze`, the colour bar in the UI |
| Missing skills ranked by importance, shown before applying or after rejection | `Recommender.demand`, `job.html`, `tracker.html` |
| Courses with links to original pages | `recommender.CourseCatalog`, `data/courses.csv` |
| Application tracking (Saved, Applied, Interview, Selected/Rejected) | `/applications` routes |
| Profile update recalculates the score | Scores are computed on request, so saving the profile is enough |

## How scoring works

- **Match %** = (matched + 0.5 x partial) / required skills. Intermediate or Advanced counts as matched,
  Beginner as partial.
- **Ranking** = 0.4 x TF-IDF cosine similarity (scaled to 0-1) + 0.6 x skill coverage. Change the
  weights in `config.py`.
- **Skill importance** = share of all jobs in the database that list the skill (market demand).
- Everything is explainable: the page shows exactly which skills drove the score.

## Where to extend it (space left on purpose)

| Improvement | Plug-in point |
|---|---|
| Live job feeds (Adzuna, Jooble, etc.) | Implement `APIJobSource.fetch()` in `job_sources.py`, call it in `refresh-jobs` (`flask --app app refresh-jobs`) |
| Better matching (Sentence-BERT, embeddings) | Replace the vectorizer inside `Recommender`; keep `rank()` / `analyze()` signatures |
| Curated courses | Add rows to `data/courses.csv` (`skill,title,platform,url`); they appear before the search links |
| PDF resume upload | Parse the PDF to text (e.g. `pypdf`) in `/profile`, then reuse `skill_dict.extract` |
| Weight skills by importance in the match % | Use `Recommender.demand` inside `analyze()` |
| Skill synonyms and new skills | Edit `data/skills.csv`; run `refresh-jobs` after adding jobs |
| Multilingual UI, mobile app, salary data | Add columns to `jobs`, new templates, or a JSON API on top of `Recommender` |
| Outcome feedback (learn from Selected/Rejected) | `applications` table already stores outcomes |
| Admin page to add or edit jobs | New blueprint using `db.load_jobs` |

## Known limits (be upfront about these in your review)

- `data/jobs.csv` holds 32 **sample** jobs from fictional companies. Replace or extend it with a real
  dataset or API before claiming real market coverage.
- Course links without curated rows fall back to Coursera, Udemy and YouTube search pages, not specific courses.
- Skill extraction is dictionary-based, so skills outside `skills.csv` are invisible to the system.
- No CSRF protection or email verification yet (Flask-WTF is the natural next step). Fine for a demo,
  not for public deployment.

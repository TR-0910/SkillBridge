"""TF-IDF + cosine ranking, skill-gap analysis, and course lookup.

To swap in a smarter model later (e.g. Sentence-BERT), keep the same public methods:
rank(), analyze(), and the `demand` dict. The Flask routes will not need to change.
"""
import csv
from collections import Counter
from urllib.parse import quote_plus

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import config


class Recommender:
    def __init__(self, jobs):
        self.jobs = jobs
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform([self._job_text(j) for j in jobs]) if jobs else None
        counts = Counter(s for j in jobs for s in j["skills"])
        n = max(len(jobs), 1)
        # demand = share of all jobs that ask for the skill; used to rank missing skills
        self.demand = {s: c / n for s, c in counts.items()}

    @staticmethod
    def _job_text(job):
        return f"{job['title']} {job['description']} " + " ".join(job["skills"] * 2)

    def analyze(self, job, levels):
        lvl_map = {k.lower(): v for k, v in levels.items()}
        matched, partial, missing = [], [], []
        for s in job["skills"]:
            lv = lvl_map.get(s.lower(), levels.get(s, 0))
            if lv >= config.MATCHED_MIN_LEVEL:
                matched.append(s)
            elif lv >= 1:
                partial.append(s)
            else:
                missing.append(s)
        missing.sort(key=lambda s: -self.demand.get(s, 0))
        total = len(job["skills"])
        coverage = (len(matched) + config.PARTIAL_CREDIT * len(partial)) / total if total else 0.0
        return {"matched": matched, "partial": partial, "missing": missing,
                "total": total, "coverage": coverage}

    def rank(self, profile_text, levels, query=None):
        if not self.jobs or not (levels or profile_text.strip()):
            return []
        sims = cosine_similarity(self.vectorizer.transform([profile_text]), self.matrix).ravel()
        top = sims.max() or 1.0
        q = (query or "").strip().lower()
        results = []
        for job, sim in zip(self.jobs, sims):
            if q and q not in f"{job['title']} {job['company']} {job['location']} {job['description']}".lower():
                continue
            a = self.analyze(job, levels)
            score = config.W_SIMILARITY * (sim / top) + config.W_COVERAGE * a["coverage"]
            results.append({**job, "similarity": float(sim), "match_pct": round(100 * a["coverage"]),
                            "rank_score": score, "analysis": a})
        results.sort(key=lambda r: r["rank_score"], reverse=True)
        return results


class CourseCatalog:
    """Curated links come from data/courses.csv; otherwise we fall back to platform searches."""

    def __init__(self, path=config.COURSES_CSV):
        self.curated = {}
        try:
            with open(path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    self.curated.setdefault(row["skill"].strip().lower(), []).append(row)
        except FileNotFoundError:
            pass

    def for_skill(self, skill, limit=3):
        q = quote_plus(skill)
        fallback = [
            {"title": f"{skill} Courses", "platform": "Coursera", "url": f"https://www.coursera.org/search?query={q}"},
            {"title": f"{skill} Certification", "platform": "NPTEL / Swayam", "url": f"https://swayam.gov.in/explorer?searchText={q}"},
            {"title": f"{skill} Tutorials", "platform": "YouTube", "url": f"https://www.youtube.com/results?search_query={q}+tutorial"},
        ]
        return (self.curated.get(skill.lower(), []) + fallback)[:limit]

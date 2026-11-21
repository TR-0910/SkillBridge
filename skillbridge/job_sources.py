"""Where jobs come from. Add a new source by subclassing JobSource."""
import csv

import config


class JobSource:
    """Return a list of dicts with: title, company, location, description, apply_url, source."""

    def fetch(self):
        raise NotImplementedError


class CSVJobSource(JobSource):
    def __init__(self, path=config.JOBS_CSV):
        self.path = path

    def fetch(self):
        with open(self.path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))


class APIJobSource(JobSource):
    """FUTURE: pull live listings from a public jobs API (Adzuna, Jooble, etc.).

    Fetch pages, map each result to the same keys as CSVJobSource, and return the list.
    db.load_jobs() already removes duplicates, so overlapping results are safe.
    """

    def fetch(self):
        raise NotImplementedError("Plug in a jobs API here.")


def dedupe(jobs):
    seen, out = set(), []
    for j in jobs:
        key = (j["title"].strip().lower(), j["company"].strip().lower(), j["location"].strip().lower())
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out

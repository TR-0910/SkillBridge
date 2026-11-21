"""Skill dictionary and text-to-skills extraction (resume and job descriptions)."""
import csv
import re

import config


class SkillDictionary:
    def __init__(self, path=config.SKILLS_CSV):
        self.category = {}      # skill -> category
        self._patterns = []     # (skill, compiled regex)
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                name = row["skill"].strip()
                self.category[name] = row["category"].strip()
                names = [name] + [a.strip() for a in row["aliases"].split(";") if a.strip()]
                alt = "|".join(
                    re.escape(n).replace(r"\ ", r"\s+") for n in sorted(names, key=len, reverse=True)
                )
                # boundaries keep "sql" out of "mysql" and "java" out of "javascript"
                self._patterns.append((name, re.compile(rf"(?<![\w+#])(?:{alt})(?![\w+#])", re.I)))

    @property
    def skills(self):
        return list(self.category)

    def grouped(self):
        """{category: [skills]} in file order, for the profile form."""
        out = {}
        for skill, cat in self.category.items():
            out.setdefault(cat, []).append(skill)
        return out

    def extract(self, text):
        text = text or ""
        return {name for name, pat in self._patterns if pat.search(text)}

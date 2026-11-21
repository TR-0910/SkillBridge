"""Central settings. Tweak weights here instead of hunting through the code."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
DATABASE = os.path.join(BASE_DIR, "career.db")
JOBS_CSV = os.path.join(BASE_DIR, "data", "jobs.csv")
SKILLS_CSV = os.path.join(BASE_DIR, "data", "skills.csv")
COURSES_CSV = os.path.join(BASE_DIR, "data", "courses.csv")

# Ranking = W_SIMILARITY * (TF-IDF cosine, scaled to 0-1) + W_COVERAGE * (skill coverage)
W_SIMILARITY = 0.4
W_COVERAGE = 0.6
PARTIAL_CREDIT = 0.5          # a Beginner-level skill counts half toward the match %
MATCHED_MIN_LEVEL = 2         # Intermediate or above counts as fully matched

LEVELS = {0: "None / Not Selected", 1: "Beginner", 2: "Intermediate", 3: "Advanced"}
STATUSES = ["Saved", "Applied", "Interview", "Selected", "Rejected"]

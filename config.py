"""
DoneHo — global config.
Loads environment variables and exposes frozen constants used across
the Deterministic Engine and agents. Do not hardcode these values
elsewhere — import from here so the whole system stays in sync.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- LLM ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
MODEL_NAME = os.getenv("DONEHO_MODEL", "gemini-2.5-flash")

# --- Frozen formula constants (Build Brief, Section 5) ---
HOURS_PER_WEEK = 168
DEFAULT_SLEEP_HOURS = 56          # 8h/day
DEFAULT_PERSONAL_CARE_HOURS = 14  # 2h/day

# Safety clamp: no single onboarding answer category (caregiving + events +
# other) may eat more than this fraction of what's left after fixed essentials.
SAFETY_CLAMP_FRACTION = 0.70

# LifeLoad
LIFELOAD_WEIGHT_TRAFFIC = 0.35
LIFELOAD_WEIGHT_VOLATILITY = 0.35
LIFELOAD_WEIGHT_COMMITMENT_RATIO = 0.30
LIFELOAD_SAFE_THRESHOLD = 65  # commit-gating threshold, 0-100 scale

# Planning Confidence
CONFIDENCE_WEIGHT_PRF = 0.4
CONFIDENCE_WEIGHT_RESERVE_RATIO = 0.3
CONFIDENCE_WEIGHT_LIFELOAD_INVERSE = 0.3

# Focus classification
FOCUS_WEIGHT_TRAFFIC = 0.65
FOCUS_WEIGHT_VOLATILITY = 0.35
FOCUS_HIGH_THRESHOLD = 0.66
FOCUS_MEDIUM_THRESHOLD = 0.33

# PRF (Planning Reliability Factor)
PRF_FIRST_WEEK_DEFAULT = 0.60
PRF_MIN = 0.10
PRF_MAX = 1.0
PRF_GOOD_COMPLETION_THRESHOLD = 0.80
PRF_GOOD_RESERVE_USAGE_CEILING = 0.30
PRF_GOOD_BONUS = 0.05
PRF_BAD_COMPLETION_THRESHOLD = 0.50
PRF_BAD_RESERVE_USAGE_FLOOR = 0.80
PRF_BAD_PENALTY = 0.07
PRF_NEUTRAL_TARGET = 0.5
PRF_NEUTRAL_PULL_FRACTION = 0.10
PRF_CAREGIVING_MAX_PENALTY = 0.20  # capped, scales with caregiving hours

# Commitment tiers: (min_prf, tier_name, factor) — checked top-down
COMMITMENT_TIERS = [
    (0.85, "Aggressive", 0.95),
    (0.70, "Normal", 0.85),
    (0.55, "Balanced", 0.75),
    (0.40, "Conservative", 0.60),
    (0.0, "Survival", 0.45),
]

# Weekly Commitment Contract range
COMMITMENT_MIN_FACTOR = 0.85
COMMITMENT_MAX_FACTOR = 1.10

# Reserve Hours
RESERVE_FIRST_WEEK_BOOST = 0.15  # +15% wider buffer, no history yet

# --- Staged Silent Absorption (Proposed Enhancements, Entry 1) ---
# Stage 2 — LifeLoad renegotiation. The conversion from "LifeLoad points"
# to "extra absorbable hours" is DERIVED from the frozen LifeLoad formula
# itself (not an arbitrary new number): the CommitmentRatio term carries a
# weight of LIFELOAD_WEIGHT_COMMITMENT_RATIO out of a 100-point scale, so
# 1 LifeLoad point from that term = 1 / (LIFELOAD_WEIGHT_COMMITMENT_RATIO * 100)
# of a CommitmentRatio point, which converts to hours via Weekly Capacity.
# See engines/absorption_engine.py for the actual conversion.
STAGE2_MAX_LIFELOAD_INCREASE_POINTS_PER_WEEK = 10  # cumulative cap, one week
# Stage 2 may never push effective LifeLoad above this ceiling. Reuses the
# same threshold as initial commit-gating (Section 5) — a mid-week
# renegotiated LifeLoad should be held to the same "safe" line a user
# would have been blocked from crossing at planning time.
STAGE2_LIFELOAD_CEILING = LIFELOAD_SAFE_THRESHOLD

# Profession fallback if not in preset list
FALLBACK_WORK_HOURS = 42
FALLBACK_COMMUTE_HOURS = 6

# --- Entry 7: Per-user pattern learning ---
# How many of the user's most recent past disruptions to include as context
# for Stage 0 cost estimation. Kept small so the prompt stays focused.
DISRUPTION_HISTORY_CONTEXT_LIMIT = 5

# --- Entry 2 (Day Output) / Entry 8 (Life Happened) ---
# If a user unticks more than this fraction of a day's tasks, Day Output
# should proactively surface the "Life Happened" option rather than
# requiring the user to seek it out.
LIFE_HAPPENED_MISS_RATIO_THRESHOLD = 0.5

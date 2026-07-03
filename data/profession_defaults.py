"""
Preset weekly (work_hours, commute_hours) by profession.
Used by CapacityEngine as a starting default — always overridable by
Profile.work_hours_override / commute_hours_override (Build Brief, Section 5).
Falls back to config.FALLBACK_WORK_HOURS / FALLBACK_COMMUTE_HOURS for
anything not listed here.
"""

PROFESSION_DEFAULTS = {
    "software engineer":        (45, 6),
    "student":                  (30, 5),
    "homemaker":                (0, 2),
    "teacher":                  (40, 6),
    "nurse":                    (45, 4),
    "business owner":           (50, 5),
    "entrepreneur":             (50, 5),
    "freelancer":               (35, 2),
    "retail worker":            (40, 5),
    "service worker":           (40, 5),
    "government employee":      (40, 5),
    "doctor":                   (55, 5),
    "healthcare professional":  (55, 5),
    "unemployed":               (10, 2),
    "job seeking":              (10, 2),
    "designer":                 (42, 5),
    "sales professional":       (45, 7),
    "consultant":               (48, 6),
    "civil servant":            (40, 5),
    "researcher / academic":    (42, 4),
    "content creator":          (35, 1),
}


def get_profession_defaults(profession: str) -> tuple[int, int]:
    """
    Case-insensitive lookup with simple substring matching, so free-text
    professions ("Sr. Software Engineer") still hit a sensible preset.
    Falls back to config defaults if nothing matches.
    """
    from config import FALLBACK_WORK_HOURS, FALLBACK_COMMUTE_HOURS

    if not profession:
        return FALLBACK_WORK_HOURS, FALLBACK_COMMUTE_HOURS

    key = profession.strip().lower()

    if key in PROFESSION_DEFAULTS:
        return PROFESSION_DEFAULTS[key]

    for preset_key, values in PROFESSION_DEFAULTS.items():
        if preset_key in key or key in preset_key:
            return values

    return FALLBACK_WORK_HOURS, FALLBACK_COMMUTE_HOURS

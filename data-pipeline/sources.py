"""Source registry for the pipeline. See README.md for provenance notes."""

# Public, crowd-sourced Ontario admissions results sheets (Google Form responses),
# one per application cycle. `year` = the fall the applicants start university
# (e.g. the 2025-2026 cycle -> students entering Sept 2026).
ADMISSIONS_SHEETS = [
    {"cycle": "2022-2023", "year": 2023,
     "sheet_id": "18xQRBO1X2llysir9GwHPhdRPeJGL-osKhOX7WC4e_3o", "gid": 1176989226},
    {"cycle": "2023-2024", "year": 2024,
     "sheet_id": "1X5oygD0Mu8v899bRBvklzB-t6saHMS7mrqfH_xsiq2Y", "gid": 1574433327},
    {"cycle": "2024-2025", "year": 2025,
     "sheet_id": "1j48oJsjcAqS9K2wQ-x-W27gYr5LuOT-a96dt_ZZpjrw", "gid": None},
    {"cycle": "2025-2026", "year": 2026,
     "sheet_id": "1NCN-1lw39N9lRyB9bJPfrkJy8v3V-yjnnZ1HjrG5I9A", "gid": None},
]


def sheet_csv_url(s):
    url = f"https://docs.google.com/spreadsheets/d/{s['sheet_id']}/export?format=csv"
    if s.get("gid") is not None:
        url += f"&gid={s['gid']}"
    return url


def sheet_view_url(s):
    url = f"https://docs.google.com/spreadsheets/d/{s['sheet_id']}/edit"
    if s.get("gid") is not None:
        url += f"#gid={s['gid']}"
    return url


# OUInfo (the official Ontario universities program catalogue). As of
# 2026-11-25 its robots.txt disallows ClaudeBot/anthropic-ai and every page
# (including robots.txt itself on ouinfo.ca) answers automated clients with a
# Cloudflare "Just a moment..." challenge. The pipeline therefore does NOT
# scrape it. build_programs.py only probes robots.txt and reports the result;
# official facts can be supplied by hand via manual/official_programs.csv.
OUINFO_BASE = "https://www.ouinfo.ca"

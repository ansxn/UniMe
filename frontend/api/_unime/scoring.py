"""MatchMe scoring: ranks university programs against a student's quiz answers."""
import json

from .schools import clean_name

# Keyword -> program-type category. Used by detect_program_type() to pick the
# PROGRAM_TYPE_WEIGHTS adjustments below.
INTEREST_MAPPINGS = {
    # Engineering related interests
    "mechanical engineering": "Engineering",
    "civil engineering": "Engineering",
    "electrical engineering": "Engineering",
    "robotics": "Engineering",
    "mechatronics": "Engineering",
    "automotive": "Engineering", 
    "aerospace": "Engineering",
    "structural design": "Engineering",
    "manufacturing": "Engineering",
    "product development": "Engineering",
    "engineering design": "Engineering",
    
    # CS/Math related interests
    "programming": "CS/Math",
    "software development": "CS/Math",
    "algorithms": "CS/Math",
    "data science": "CS/Math",
    "mathematics": "CS/Math",
    "statistics": "CS/Math",
    "computer science": "CS/Math",
    "web development": "CS/Math",
    "artificial intelligence": "CS/Math",
    "machine learning": "CS/Math",
    "cryptography": "CS/Math",
    "cybersecurity": "CS/Math",
    "computational": "CS/Math",
    
    # Business related interests
    "finance": "Business",
    "marketing": "Business",
    "entrepreneurship": "Business",
    "economics": "Business",
    "accounting": "Business",
    "management": "Business",
    "business": "Business",
    "consulting": "Business",
    "human resources": "Business",
    "sales": "Business",
    "investment": "Business",
    "stock market": "Business",
    "taxation": "Business",
    "audit": "Business",
    
    # Arts/Humanities related interests
    "literature": "Arts/Humanities",
    "philosophy": "Arts/Humanities",
    "history": "Arts/Humanities",
    "languages": "Arts/Humanities",
    "writing": "Arts/Humanities",
    "cultural studies": "Arts/Humanities",
    "art history": "Arts/Humanities",
    "music": "Arts/Humanities",
    "film": "Arts/Humanities",
    "theatre": "Arts/Humanities",
    "creative writing": "Arts/Humanities",
    "linguistics": "Arts/Humanities",
    "anthropology": "Arts/Humanities",
    "archaeology": "Arts/Humanities",
    
    # Sciences related interests
    "biology": "Sciences",
    "chemistry": "Sciences",
    "physics": "Sciences",
    "environmental science": "Sciences",
    "astronomy": "Sciences",
    "earth sciences": "Sciences",
    "geology": "Sciences",
    "biochemistry": "Sciences",
    "molecular biology": "Sciences",
    "genetics": "Sciences",
    "ecology": "Sciences",
    "marine biology": "Sciences",
    "forensic science": "Sciences",
    
    # Health related interests
    "medicine": "Health",
    "nursing": "Health",
    "kinesiology": "Health",
    "public health": "Health",
    "nutrition": "Health",
    "psychology": "Health",
    "healthcare": "Health",
    "anatomy": "Health",
    "physiology": "Health",
    "pharmacy": "Health",
    "biomedical": "Health",
    "dentistry": "Health",
    "therapy": "Health",
    "mental health": "Health",
    "psychiatry": "Health",
    "rehabilitation": "Health"
}

# Course mappings - connect high school courses to program preferences
COURSE_MAPPINGS = {
    "calculus": "Math",
    "algebra": "Math",
    "statistics": "Math",
    "physics": "Physics",
    "biology": "Biology",
    "chemistry": "Chemistry",
    "computer programming": "Computer Science",
    "business studies": "Business",
    "economics": "Business",
    "english": "Language Arts",
    "literature": "Language Arts",
    "creative writing": "Language Arts",
    "history": "History",
    "geography": "Geography",
    "art": "Visual Arts",
    "visual arts": "Visual Arts",
    "design": "Visual Arts",
    "shop class": "Autoshop",
    "auto mechanics": "Autoshop"
}


PROGRAM_TYPE_WEIGHTS = {
    'Engineering': {
        'math_enjoyment': 1.8,
        'learning_style': 1.4,  # Hands-on important for engineering
        'coop_importance': 1.3,
        'creativity_orientation': 1.0
    },
    'CS/Math': {
        'math_enjoyment': 1.7,
        'collaboration_preference': 1.2,
        'coop_importance': 1.3
    },
    'Business': {
        'collaboration_preference': 1.5,
        'career_certainty': 1.3,
        'coop_importance': 1.4
    },
    'Arts/Humanities': {
        'creativity_orientation': 1.8,
        'math_enjoyment': 0.7,  # Less important
        'research_importance': 1.3
    },
    'Sciences': {
        'research_importance': 1.6,
        'math_enjoyment': 1.4,
        'learning_style': 1.3
    },
    'Health': {
        'collaboration_preference': 1.4,
        'research_importance': 1.3,
        'career_certainty': 1.2
    }
}


# String normalization for consistent matching
def normalize_string(s):
    """Normalize strings for comparison by lowercasing and replacing separators"""
    if not s:
        return ""
    return s.lower().replace('-', ' ').replace('/', ' ').replace('_', ' ').strip()

# Detect program type from interests
def detect_program_type(program):
    """Detect the primary type of a program based on its interests"""
    interests = program.get('academic', {}).get('interests', [])
    program_name = program.get('program', '').lower()
    
    # Count category matches
    category_counts = {}
    for interest in interests:
        interest_lower = interest.lower()
        for key_term, category in INTEREST_MAPPINGS.items():
            if key_term in interest_lower:
                category_counts[category] = category_counts.get(category, 0) + 1
                break
    
    # Also check program name for hints
    name_hints = {
        'Engineering': ['engineering', 'mechanical', 'electrical', 'civil', 'chemical'],
        'CS/Math': ['computer', 'software', 'math', 'data science', 'computing'],
        'Business': ['business', 'commerce', 'management', 'finance', 'accounting', 'marketing'],
        'Arts/Humanities': ['arts', 'humanities', 'english', 'philosophy', 'history', 'music'],
        'Sciences': ['science', 'biology', 'chemistry', 'physics', 'environmental'],
        'Health': ['health', 'nursing', 'medicine', 'kinesiology', 'pharmacy']
    }
    
    for category, hints in name_hints.items():
        for hint in hints:
            if hint in program_name:
                category_counts[category] = category_counts.get(category, 0) + 2
    
    if not category_counts:
        return None
    
    return max(category_counts, key=category_counts.get)

# Enhanced interest matching using mappings with continuous scoring

# Enhanced course matching using mappings with normalization
def enhanced_course_score(user_courses, program_courses):
    """Calculate course match score with improved mapping and normalization"""
    if not user_courses or not program_courses:
        return 0
    
    # Normalize user courses for comparison
    user_courses_normalized = {normalize_string(c) for c in user_courses}
    
    total_score = 0.0
    matched_courses = set()
    
    for course in program_courses:
        course_normalized = normalize_string(course)
        
        # Direct match = full points
        if course_normalized in user_courses_normalized:
            total_score += 1.0
            matched_courses.add(course_normalized)
            continue
        
        # Try mapped categories with partial credit
        for key_term, category in COURSE_MAPPINGS.items():
            if key_term in course_normalized:
                category_normalized = normalize_string(category)
                if category_normalized in user_courses_normalized or category in user_courses:
                    if category_normalized not in matched_courses:
                        total_score += 0.8  # Good partial credit for category match
                        matched_courses.add(category_normalized)
                    break
    
    match_ratio = total_score / max(len(user_courses), 1)
    return min(match_ratio, 1.0)  # Cap at 1.0

# Confidence weighting for Likert responses
def calculate_trait_score_with_confidence(user_val, prog_val):
    """Calculate similarity score with confidence weighting based on response extremity"""
    # Base similarity (0 to 1)
    similarity = 1 - (abs(prog_val - user_val) / 4.0)
    
    # Users with neutral answers (3) care less about this dimension
    # Importance ranges from 0.0 (neutral) to 1.0 (extreme)
    importance = abs(user_val - 3) / 2.0
    
    # Confidence weight ranges from 0.6 to 1.0
    # Neutral responses still contribute, but less decisively
    confidence_weight = 0.6 + (importance * 0.4)
    
    return similarity * confidence_weight

# Distance-based scoring for categorical values
def score_categorical_distance(user_pref, prog_val, order_list):
    """Score based on distance in ordered categories"""
    if user_pref not in order_list or prog_val not in order_list:
        return 0.5  # Neutral if unknown
    
    user_idx = order_list.index(user_pref)
    prog_idx = order_list.index(prog_val)
    max_distance = len(order_list) - 1
    
    if max_distance == 0:
        return 1.0
    
    distance = abs(user_idx - prog_idx)
    # Gradual falloff based on distance
    return 1.0 - (distance / max_distance) * 0.7



# ---------------------------------------------------------------------------
# Interest matching
#
# The quiz's "AA" question sends these values. Each maps to keywords that are
# matched (as substrings) against a program's `academic.interests` list. A
# keyword can belong to several areas (e.g. biology is both health/life
# sciences and natural sciences).
# ---------------------------------------------------------------------------
QUIZ_INTEREST_KEYWORDS = {
    "engineering": [
        "engineering", "mechanical", "civil", "electrical", "robotics", "mechatronics",
        "automotive", "aerospace", "structural", "manufacturing", "product development",
    ],
    "cs-math": [
        "computer", "computing", "computational", "programming", "software", "algorithm",
        "data science", "data analysis", "mathematics", "math", "statistics",
        "artificial intelligence", "machine learning", "cryptography", "cybersecurity",
        "technology",
    ],
    "business": [
        "business", "finance", "marketing", "entrepreneurship", "economics", "accounting",
        "management", "consulting", "human resources", "sales", "investment", "commerce",
        "taxation", "audit",
    ],
    "health": [
        "health", "medicine", "medical", "nursing", "kinesiology", "nutrition", "anatomy",
        "physiology", "pharmacy", "biomedical", "dentistry", "therapy", "rehabilitation",
        "biology", "life science", "biochemistry", "genetics",
    ],
    "sciences": [
        "science", "biology", "chemistry", "physics", "environmental", "astronomy", "earth",
        "geology", "biochemistry", "molecular", "genetics", "ecology", "forensic",
    ],
    "social-sciences": [
        "psychology", "sociology", "social science", "anthropology", "human behavior",
        "criminology", "social work", "geography", "political science", "politics",
        "social issues", "social structures",
    ],
    "arts-humanities": [
        "arts", "literature", "philosophy", "history", "languages", "writing", "culture",
        "cultural", "music", "film", "theatre", "linguistics", "archaeology", "design",
        "media", "communication", "humanities", "fine art", "visual",
    ],
    "education-law": [
        "education", "teaching", "law", "legal", "justice", "policy", "government",
        "governance", "political", "policing", "public administration",
    ],
}

UNDECIDED = "undecided"


def enhanced_interest_score(user_interests, program_interests):
    """Score 0..1 for how well a program's interests cover the user's chosen areas.

    For each chosen area: 1 matching program interest = 0.75, 2+ = 1.0.
    "undecided" contributes a neutral 0.5 so it doesn't zero out every program.
    """
    picks = [normalize_string(i).replace(" ", "-") for i in (user_interests or [])]
    picks = [p for p in picks if p]
    if not picks:
        return 0.0

    prog = [normalize_string(i) for i in (program_interests or [])]
    scores = []
    for pick in picks:
        if pick == UNDECIDED:
            scores.append(0.5)
            continue
        keywords = QUIZ_INTEREST_KEYWORDS.get(pick)
        if keywords is None:
            # Unknown value: fall back to a direct name match
            hits = sum(1 for i in prog if pick.replace("-", " ") in i)
        else:
            hits = sum(1 for i in prog if any(k in i for k in keywords))
        scores.append(0.0 if hits == 0 else (0.75 if hits == 1 else 1.0))
    return sum(scores) / len(scores)


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------
class InvalidAnswer(ValueError):
    """Raised for malformed quiz answers; the API turns this into a 400."""


def _likert(answers, key, default=3):
    raw = answers.get(key, default)
    try:
        val = int(float(raw))
    except (TypeError, ValueError):
        raise InvalidAnswer(f"'{key}' must be a number from 1 to 5")
    if not 1 <= val <= 5:
        raise InvalidAnswer(f"'{key}' must be between 1 and 5")
    return val


def _weight(answers, key):
    raw = answers.get(key, 1)
    try:
        val = float(raw)
    except (TypeError, ValueError):
        raise InvalidAnswer(f"'{key}' must be a number")
    if val < 0:
        raise InvalidAnswer(f"'{key}' must not be negative")
    return val


def _list(answers, key):
    raw = answers.get(key, [])
    if isinstance(raw, str):
        return [raw] if raw else []
    if not isinstance(raw, list):
        raise InvalidAnswer(f"'{key}' must be a list")
    return [str(x) for x in raw]


def _str(answers, key):
    raw = answers.get(key, "")
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    return str(raw)


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------
NEUTRAL = 0.5  # score used when a program is missing the data for a factor


def compute_matches(programs, answers, num_results=10):
    if not isinstance(answers, dict):
        raise InvalidAnswer("Request body must be a JSON object")

    wa, wc, wso = _weight(answers, "wa"), _weight(answers, "wc"), _weight(answers, "wso")
    if wa + wc + wso == 0:
        wa = wc = wso = 1.0
    w_total = wa + wc + wso

    AA = _list(answers, "AA")
    LC = _list(answers, "LC")
    ALT = _list(answers, "ALT")
    HS = {normalize_string(h) for h in _list(answers, "HS")}
    CLB = {normalize_string(c) for c in _list(answers, "CLB")} - {"none"}
    SPT = normalize_string(_str(answers, "SPT"))
    CSB, SET, CPS = _str(answers, "CSB"), _str(answers, "SET"), _str(answers, "CPS")
    LS, SP, CO, UR = (_likert(answers, k) for k in ("LS", "SP", "CO", "UR"))
    CR, CE, ME, CP = (_likert(answers, k) for k in ("CR", "CE", "ME", "CP"))
    NS, CEV = _likert(answers, "NS"), _likert(answers, "CEV")

    trait_keys = ['learning_style', 'first_year_specialization', 'coop_importance',
                  'research_importance', 'creativity_orientation', 'career_certainty',
                  'math_enjoyment', 'collaboration_preference']
    trait_vals = [LS, SP, CO, UR, CR, CE, ME, CP]
    user_alt = {normalize_string(a) for a in ALT}

    def score_academic(p):
        acad = p.get('academic', {})
        i_score = enhanced_interest_score(AA, acad.get('interests', [])) * 0.4
        lc_score = enhanced_course_score(LC, acad.get('liked_hs_courses', [])) * 0.2

        alt_score = 0
        if user_alt:
            prog_alt = {normalize_string(a) for a in acad.get('alt_to_engineering', [])}
            alt_score = (len(prog_alt & user_alt) / len(user_alt)) * 0.1

        weights = {
            'learning_style': 1.2,
            'first_year_specialization': 1.0,
            'coop_importance': 1.5 if CO >= 4 else 1.0,
            'research_importance': 1.5 if UR >= 4 else 1.0,
            'creativity_orientation': 1.2 if CR >= 4 else 1.0,
            'career_certainty': 1.0,
            'math_enjoyment': 1.3,
            'collaboration_preference': 1.0,
        }
        program_type = detect_program_type(p)
        for key, multiplier in PROGRAM_TYPE_WEIGHTS.get(program_type, {}).items():
            if key in weights:
                weights[key] *= multiplier

        total_weight = sum(weights.values())
        num_score = sum(
            calculate_trait_score_with_confidence(v, acad.get(k, 3)) * weights[k]
            for k, v in zip(trait_keys, trait_vals)
        ) / total_weight * 0.3
        return i_score + lc_score + num_score + alt_score

    def score_campus(p):
        base = p.get('campus') or {}
        scores = []

        prog_csb = base.get('class_size_bin')
        scores.append(score_categorical_distance(CSB, prog_csb, ["< 60", "60-200", "200+"])
                      if prog_csb else NEUTRAL)

        prog_set = normalize_string(base.get('setting', ''))
        user_set = normalize_string(SET)
        if not prog_set or not user_set:
            scores.append(NEUTRAL)
        else:
            scores.append(score_categorical_distance(
                user_set, prog_set, ['urban', 'suburban', 'small town', 'rural']))

        prog_hs = {normalize_string(h) for h in base.get('housing_styles', [])}
        if not HS or not prog_hs:
            scores.append(NEUTRAL)
        else:
            scores.append(len(HS & prog_hs) / len(HS))

        prog_cps = base.get('campus_size')
        scores.append(score_categorical_distance(
            CPS.capitalize(), prog_cps.capitalize(), ["Small", "Medium", "Large"])
            if prog_cps and CPS else NEUTRAL)

        return sum(scores) / len(scores)

    def score_social(p):
        base = p.get('social') or {}
        ns_score = calculate_trait_score_with_confidence(NS, base.get('night_scene', 3))

        # SPT is one of: none | rec | varsity. Programs list the sports offered.
        sports = {normalize_string(s) for s in base.get('sports', [])} - {"none"}
        if SPT in ("", "none"):
            spt_score = 1.0
        elif SPT == "rec":
            spt_score = 1.0 if sports else 0.3
        else:  # varsity: reward schools with a broad sports programme
            spt_score = min(len(sports) / 4, 1.0)

        prog_clubs = {normalize_string(c) for c in base.get('clubs', [])}
        cl_score = len(prog_clubs & CLB) / len(CLB) if CLB else NEUTRAL

        cev_score = calculate_trait_score_with_confidence(CEV, base.get('cultural_event_freq', 3))
        return (ns_score + spt_score + cl_score + cev_score) / 4

    results = []
    for p in programs:
        a, c, s = score_academic(p), score_campus(p), score_social(p)
        results.append({
            "school": p['uni'],
            "program": p['program'],
            "overall": (wa * a + wc * c + wso * s) / w_total,
            "academic": a,
            "campus": c,
            "social": s,
        })
    results.sort(key=lambda x: x["overall"], reverse=True)
    return results[:num_results]


def load_programs(path):
    """Load program profiles, normalizing school names and dropping duplicates."""
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    seen, programs = set(), []
    for p in raw:
        p['uni'] = clean_name(p['uni'])
        key = (p['uni'], p['program'])
        if key in seen:
            continue
        seen.add(key)
        programs.append(p)
    return programs

"""Job categories, so a user can say which kinds of work to show and which to
never scan again.

The categories are the 23 major groups of the O*NET-SOC 2019 taxonomy, the US
Department of Labor's standard occupational classification. They are used here
because they are neutral: they cover every profession rather than the ones one
developer happened to think of, they are the vocabulary employers and labour
statistics already use, and they are short enough to fit in a settings panel.

O*NET-SOC Taxonomy by the U.S. Department of Labor, Employment and Training
Administration, used under CC BY 4.0. https://www.onetcenter.org/taxonomy.html

Classification here is deliberately simple: weighted keyword matching against
the job title first, the description second. A title is a far stronger signal
than a description -- "Staff Nurse" tells you more than three paragraphs about
a hospital's mission -- so title hits count for much more. Anything that does
not clear the confidence floor is left as "unclassified" rather than guessed,
because a wrong category can hide a job the user wanted.
"""
from __future__ import annotations

import re

# code -> (display name, title keywords, description keywords)
# Keywords are lowercase substrings matched against normalised text.
CATEGORIES: dict[str, dict] = {
    "management": {
        "name": "Management",
        "title": [
            "chief executive", "ceo", "coo", "cto", "cfo", "managing director",
            "general manager", "operations manager", "director of", "head of",
            "vp ", "vice president", "branch manager", "program manager",
            "project manager", "product manager", "product owner",
            "portfolio manager", "chief of staff",
        ],
        "desc": ["p&l", "budget ownership", "lead a team", "direct reports"],
    },
    "business_finance": {
        "name": "Business & Financial Operations",
        "title": [
            "accountant", "auditor", "financial analyst", "business analyst",
            "budget analyst", "credit analyst", "compliance", "buyer",
            "procurement", "purchasing", "human resources", "hr ", "recruiter",
            "talent acquisition", "training", "logistician", "claims adjuster",
            "tax ", "treasury", "fp&a", "management consultant",
            "operations analyst", "risk analyst",
        ],
        "desc": ["gaap", "financial statements", "forecasting", "payroll"],
    },
    "computer_math": {
        "name": "Computer & Mathematical",
        "title": [
            "software engineer", "software developer", "developer", "programmer",
            "data scientist", "data engineer", "data analyst", "analytics engineer",
            "machine learning", "ml engineer", "ai engineer", "devops",
            "site reliability", "sre", "systems administrator", "network engineer",
            "database administrator", "security engineer", "cybersecurity",
            "qa engineer", "test engineer", "web developer", "mobile developer",
            "ios ", "android ", "full stack", "backend", "frontend", "statistician",
            "actuary", "mathematician", "cloud engineer", "platform engineer",
        ],
        "desc": ["python", "javascript", "kubernetes", "sql", "api", "git"],
    },
    "architecture_engineering": {
        "name": "Architecture & Engineering",
        "title": [
            "architect", "civil engineer", "mechanical engineer",
            "electrical engineer", "chemical engineer", "aerospace engineer",
            "industrial engineer", "structural engineer", "process engineer",
            "manufacturing engineer", "petroleum engineer", "drafter",
            "surveyor", "engineering technician", "biomedical engineer",
        ],
        "desc": ["cad", "autocad", "tolerance", "schematic", "pe license"],
    },
    "science": {
        "name": "Life, Physical & Social Science",
        "title": [
            "scientist", "chemist", "biologist", "physicist", "geologist",
            "microbiologist", "epidemiologist", "economist", "psychologist",
            "research associate", "research scientist", "lab technician",
            "laboratory", "clinical research", "environmental scientist",
        ],
        "desc": ["peer-reviewed", "hypothesis", "assay", "specimen", "phd"],
    },
    "community_social": {
        "name": "Community & Social Service",
        "title": [
            "social worker", "counselor", "counsellor", "case manager",
            "community health worker", "probation officer", "chaplain",
            "clergy", "youth worker", "substance abuse", "outreach worker",
        ],
        "desc": ["caseload", "safeguarding", "client advocacy"],
    },
    "legal": {
        "name": "Legal",
        "title": [
            "lawyer", "attorney", "solicitor", "barrister", "paralegal",
            "legal counsel", "general counsel", "legal assistant",
            "court reporter", "judge", "mediator", "title examiner",
        ],
        "desc": ["litigation", "contract review", "bar admission", "deposition"],
    },
    "education": {
        "name": "Education & Library",
        "title": [
            "teacher", "professor", "lecturer", "instructor", "tutor",
            "principal", "librarian", "teaching assistant", "curriculum",
            "academic advisor", "school counselor", "dean", "educator",
        ],
        "desc": ["lesson plan", "curriculum", "pupils", "students", "classroom"],
    },
    "arts_media": {
        "name": "Arts, Design, Media & Sport",
        "title": [
            "designer", "graphic design", "ux ", "ui ", "product design",
            "art director", "writer", "editor", "journalist", "reporter",
            "photographer", "videographer", "video editor", "animator",
            "musician", "producer", "content creator", "copywriter",
            "social media", "public relations", "broadcast", "athlete", "coach",
        ],
        "desc": ["figma", "adobe", "portfolio", "editorial", "brand voice"],
    },
    "healthcare_practitioner": {
        "name": "Healthcare Practitioners & Technical",
        "title": [
            "nurse", "rn ", "physician", "doctor", "surgeon", "dentist",
            "pharmacist", "physical therapist", "occupational therapist",
            "radiologic", "veterinarian", "paramedic", "midwife", "optometrist",
            "dietitian", "respiratory therapist", "speech language pathologist",
            "physician assistant", "nurse practitioner", "sonographer",
        ],
        "desc": ["patient care", "clinical", "diagnosis", "licensure", "bedside"],
    },
    "healthcare_support": {
        "name": "Healthcare Support",
        "title": [
            "nursing assistant", "home health aide", "medical assistant",
            "dental assistant", "dental hygienist", "orderly", "phlebotomist",
            "pharmacy technician", "caregiver", "patient care technician",
        ],
        "desc": ["vital signs", "assist patients", "personal care"],
    },
    "protective": {
        "name": "Protective Service",
        "title": [
            "police officer", "firefighter", "security guard", "security officer",
            "correctional officer", "detective", "bailiff", "lifeguard",
            "loss prevention", "emergency management",
        ],
        "desc": ["patrol", "incident report", "public safety"],
    },
    "food_service": {
        "name": "Food Preparation & Serving",
        "title": [
            "chef", "cook", "baker", "bartender", "barista", "server",
            "waiter", "waitress", "dishwasher", "food service",
            "restaurant manager", "kitchen",
        ],
        "desc": ["food safety", "menu", "line cook", "front of house"],
    },
    "facilities": {
        "name": "Building & Grounds Maintenance",
        "title": [
            "janitor", "custodian", "cleaner", "housekeeper", "groundskeeper",
            "landscaper", "pest control", "facilities",
        ],
        "desc": ["sanitation", "grounds", "cleaning schedule"],
    },
    "personal_care": {
        "name": "Personal Care & Service",
        "title": [
            "hairdresser", "barber", "cosmetologist", "manicurist",
            "fitness trainer", "personal trainer", "childcare", "nanny",
            "animal care", "funeral", "concierge", "tour guide", "esthetician",
        ],
        "desc": ["clientele", "appointments", "salon"],
    },
    "sales": {
        "name": "Sales & Related",
        "title": [
            "sales", "account executive", "account manager", "business development",
            "partnerships", "retail associate", "cashier", "real estate agent",
            "insurance agent", "sales engineer", "customer success",
            "telemarketer", "merchandiser", "sales representative",
        ],
        "desc": ["quota", "pipeline", "crm", "close deals", "prospecting"],
    },
    "admin_support": {
        "name": "Office & Administrative Support",
        "title": [
            "administrative assistant", "executive assistant", "receptionist",
            "office manager", "data entry", "secretary", "clerk", "scheduler",
            "customer service", "call center", "support specialist",
            "dispatcher", "bookkeeper", "billing",
        ],
        "desc": ["calendar management", "filing", "inbound calls", "ticketing"],
    },
    "farming": {
        "name": "Farming, Fishing & Forestry",
        "title": [
            "farm", "farmworker", "agricultural", "forester", "logger",
            "fisher", "rancher", "greenhouse", "agronomist",
        ],
        "desc": ["harvest", "livestock", "crop", "irrigation"],
    },
    "construction": {
        "name": "Construction & Extraction",
        "title": [
            "carpenter", "electrician", "plumber", "welder", "mason",
            "roofer", "painter", "construction", "site supervisor",
            "heavy equipment operator", "miner", "driller", "pipefitter",
            "glazier", "ironworker",
        ],
        "desc": ["blueprint", "job site", "osha", "scaffold"],
    },
    "maintenance_repair": {
        "name": "Installation, Maintenance & Repair",
        "title": [
            "mechanic", "technician", "hvac", "millwright", "maintenance",
            "field service", "repair", "installer", "elevator", "locksmith",
            "avionics", "automotive",
        ],
        "desc": ["preventive maintenance", "troubleshoot equipment", "calibration"],
    },
    "production": {
        "name": "Production & Manufacturing",
        "title": [
            "machinist", "assembler", "production operator", "machine operator",
            "fabricator", "quality inspector", "tailor", "printing",
            "plant operator", "cnc", "production supervisor", "butcher",
        ],
        "desc": ["assembly line", "shift work", "production quota", "lean"],
    },
    "transport": {
        "name": "Transportation & Material Moving",
        "title": [
            "driver", "truck driver", "delivery", "courier", "pilot",
            "flight attendant", "warehouse", "forklift", "material handler",
            "shipping", "logistics coordinator", "captain", "conductor",
            "dispatcher", "packer",
        ],
        "desc": ["cdl", "route", "pallet", "loading dock"],
    },
    "military": {
        "name": "Military Specific",
        "title": ["military", "armed forces", "infantry", "naval", "air crew"],
        "desc": ["deployment", "combat", "rank"],
    },
}

UNCLASSIFIED = "unclassified"
UNCLASSIFIED_NAME = "Unclassified"

# A title hit is worth this much more than a description hit. A description
# mentioning "python" does not make a recruiting role a software job.
_TITLE_WEIGHT = 6
_DESC_WEIGHT = 1
# Below this, say "unclassified" rather than guess. A wrong category can hide a
# job the user wanted, which is worse than an honest blank.
_MIN_CONFIDENCE = 4

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    """Lowercase, pad with spaces so ' hr ' style keywords match at the edges."""
    return " " + _WS.sub(" ", (text or "").lower().replace("/", " ")).strip() + " "


def category_list() -> list[dict]:
    """Every category, for the settings picker."""
    return [
        {"code": code, "name": spec["name"]} for code, spec in CATEGORIES.items()
    ] + [{"code": UNCLASSIFIED, "name": UNCLASSIFIED_NAME}]


def category_name(code: str) -> str:
    if code == UNCLASSIFIED:
        return UNCLASSIFIED_NAME
    spec = CATEGORIES.get(code)
    return spec["name"] if spec else UNCLASSIFIED_NAME


def classify(title: str, description: str = "") -> str:
    """Best-effort category code for a posting. Returns UNCLASSIFIED when no
    category clears the confidence floor."""
    t = _norm(title)
    d = _norm(description)[:4000]  # the opening of a JD carries the signal

    best_code = UNCLASSIFIED
    best_score = 0
    for code, spec in CATEGORIES.items():
        score = 0
        for kw in spec["title"]:
            if kw in t:
                score += _TITLE_WEIGHT
        for kw in spec["desc"]:
            if kw in d:
                score += _DESC_WEIGHT
        if score > best_score:
            best_score, best_code = score, code

    return best_code if best_score >= _MIN_CONFIDENCE else UNCLASSIFIED

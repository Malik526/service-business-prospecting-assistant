"""Target service business categories and filtering helpers for prospect discovery.

Each category defines:
  - name:       Human-readable label stored in the Google Sheet.
  - query:      Search string sent to the Google Places Text Search API.
  - high_ticket: Heuristic flag — see below.
  - crm_fit:    Heuristic flag — see below.

IMPORTANT: high_ticket and crm_fit are generalized operational assumptions.
They are NOT objective truth, NOT market-validated, and NOT statistically
derived. They reflect reasonable generalizations about how these business
types tend to operate, based on common industry knowledge.

high_ticket
-----------
True when the category is heuristically associated with higher average
transaction values. Higher ticket size means greater ROI on marketing,
CRM, or lead capture tools — making these businesses stronger outreach
candidates for digital growth services.

  True examples:
    - Dentists:       Treatment plans and cosmetic work are often $500–$5,000+.
    - Med spas:       Procedures like Botox, fillers, or laser are $300–$2,000+ each.
    - Caterers:       Event bookings are typically $1,000–$20,000+ per event.
    - HVAC/Plumbers:  Emergency and installation jobs commonly run $500–$5,000+.
    - Contractors:    Renovation and construction projects are often $5,000–$100,000+.
    - Electricians:   Panel upgrades and rewiring often $1,000–$10,000+.
    - Exterminators:  Recurring service contracts and remediation can be high value.
    - Event planners: Full-service event coordination is typically $2,000–$20,000+.
    - Photographers:  Wedding and commercial photography often $1,000–$10,000+.
    - Videographers:  Wedding and commercial video production often $2,000–$15,000+.

  False examples:
    - Salons/Barbers:      Typically lower per-visit revenue ($30–$150).
    - Fitness studios/Gyms: Membership-based; lower per-transaction value.
    - Cleaning companies:  Recurring but lower per-visit cost ($100–$300).
    - Massage/Spas:        Per-session cost is moderate ($80–$200).

crm_fit
-------
True when the category clearly benefits from appointment booking, automated
follow-up, lead capture, or customer retention tools. Almost all service
businesses benefit from some form of CRM, but crm_fit=True signals categories
where the operational need is especially pronounced and the ROI of a CRM or
automation tool is easiest to demonstrate.

Examples of why crm_fit matters:
  - Caterers:     Rely heavily on quote requests, inquiry tracking, and event timelines.
  - Med spas:     Depend on appointment booking, rebooking reminders, and retention.
  - Plumbers/HVAC: Urgent lead capture is critical — a missed call is a lost job.
  - Dentists:     Need appointment reminders, follow-ups, and recall campaigns.
  - Salons:       Appointment scheduling and rebooking reminders drive repeat revenue.
  - Fitness:      Membership retention, class scheduling, and lead nurture are key.

Currently, all TARGET_CATEGORIES have crm_fit=True because this tool is
specifically designed for outreach to businesses that can benefit from
digital growth and CRM-adjacent services.
"""

TARGET_CATEGORIES = [
    {
        "name": "catering",
        "query": "catering",
        "high_ticket": True,   # Event catering bookings are typically $1,000–$20,000+
        "crm_fit": True,       # Inquiry tracking, quote follow-up, and event timelines are core ops
    },
    {
        "name": "photographers",
        "query": "photographer",
        "high_ticket": True,   # Wedding/commercial photography: $1,000–$10,000+ per booking
        "crm_fit": True,       # Inquiry pipeline, contract follow-up, and gallery delivery tracking
    },
    {
        "name": "videographers",
        "query": "videographer",
        "high_ticket": True,   # Wedding/commercial video: $2,000–$15,000+ per project
        "crm_fit": True,       # Inquiry pipeline and project milestone follow-up
    },
    {
        "name": "med spas",
        "query": "med spa",
        "high_ticket": True,   # Cosmetic procedures (Botox, fillers, laser): $300–$2,000+ per visit
        "crm_fit": True,       # Appointment booking, rebooking reminders, and retention sequences
    },
    {
        "name": "massage spas",
        "query": "massage spa",
        "high_ticket": False,  # Per-session cost is moderate ($80–$200); not classified as high-ticket
        "crm_fit": True,       # Appointment scheduling and rebooking reminders drive repeat visits
    },
    {
        "name": "spas",
        "query": "spa",
        "high_ticket": False,  # General spas have moderate per-visit revenue
        "crm_fit": True,       # Booking and retention tools are directly applicable
    },
    {
        "name": "plumbers",
        "query": "plumber",
        "high_ticket": True,   # Emergency calls and installations: $500–$5,000+ per job
        "crm_fit": True,       # Urgent lead capture is critical — missed calls are missed revenue
    },
    {
        "name": "HVAC",
        "query": "HVAC contractor",
        "high_ticket": True,   # System installs and repairs: $500–$10,000+ per job
        "crm_fit": True,       # Lead capture, seasonal campaigns, and maintenance reminders
    },
    {
        "name": "exterminators",
        "query": "exterminator",
        "high_ticket": True,   # Remediation and recurring contracts can be high value
        "crm_fit": True,       # Recurring service follow-up and new inquiry capture
    },
    {
        "name": "electricians",
        "query": "electrician",
        "high_ticket": True,   # Panel upgrades and rewiring: $1,000–$10,000+
        "crm_fit": True,       # Lead capture and follow-up for quote requests
    },
    {
        "name": "cleaning companies",
        "query": "cleaning company",
        "high_ticket": False,  # Per-visit cost is lower ($100–$300); recurring but not high-ticket
        "crm_fit": True,       # Recurring scheduling, client retention, and referral follow-up
    },
    {
        "name": "contractors",
        "query": "contractor",
        "high_ticket": True,   # Renovation and construction projects: $5,000–$100,000+
        "crm_fit": True,       # Quote pipeline, project follow-up, and referral tracking
    },
    {
        "name": "salons",
        "query": "hair salon",
        "high_ticket": False,  # Per-visit revenue is lower ($30–$150); appointment volume is the driver
        "crm_fit": True,       # Appointment scheduling, rebooking reminders, and seasonal promotions
    },
    {
        "name": "barbers",
        "query": "barber shop",
        "high_ticket": False,  # Lower per-visit revenue ($25–$80); volume-driven business
        "crm_fit": True,       # Appointment booking and loyalty/retention tools apply
    },
    {
        "name": "fitness studios",
        "query": "fitness studio",
        "high_ticket": False,  # Membership-based; lower per-transaction value
        "crm_fit": True,       # Membership retention, class scheduling, and lead nurture are key
    },
    {
        "name": "gyms",
        "query": "gym",
        "high_ticket": False,  # Monthly memberships are lower per-transaction
        "crm_fit": True,       # Lead nurture for trials, membership retention, and reactivation
    },
    {
        "name": "dentists",
        "query": "dentist",
        "high_ticket": True,   # Treatment plans and cosmetic work: $500–$5,000+ per case
        "crm_fit": True,       # Appointment reminders, recall campaigns, and follow-up sequences
    },
    {
        "name": "event planners",
        "query": "event planner",
        "high_ticket": True,   # Full-service event coordination: $2,000–$20,000+ per event
        "crm_fit": True,       # Inquiry tracking, vendor coordination, and client follow-up
    },
]


def normalize_category_key(value: str) -> str:
    """Normalize category names, queries, and CLI tokens for loose matching."""
    return "".join(character for character in value.lower() if character.isalnum())


def _category_lookup() -> dict[str, dict]:
    """Build a lookup that accepts canonical names, queries, and singular forms."""
    lookup = {}

    for category in TARGET_CATEGORIES:
        keys = {
            normalize_category_key(category["name"]),
            normalize_category_key(category["query"]),
        }

        for key in list(keys):
            if key.endswith("ies"):
                keys.add(f"{key[:-3]}y")
            if key.endswith("s"):
                keys.add(key[:-1])

        for key in keys:
            lookup.setdefault(key, category)

    return lookup


def filter_target_categories(category_names: str | None) -> list[dict]:
    """Return target categories matching a comma-separated CLI category list."""
    if not category_names:
        return TARGET_CATEGORIES

    requested_names = [name.strip() for name in category_names.split(",") if name.strip()]
    if not requested_names:
        raise ValueError("Provide at least one category after --categories.")

    lookup = _category_lookup()
    selected_categories = []
    seen_names = set()
    unknown_names = []

    for requested_name in requested_names:
        category = lookup.get(normalize_category_key(requested_name))
        if not category:
            unknown_names.append(requested_name)
            continue

        if category["name"] in seen_names:
            continue

        selected_categories.append(category)
        seen_names.add(category["name"])

    if unknown_names:
        available_names = ", ".join(category["name"] for category in TARGET_CATEGORIES)
        unknown_display = ", ".join(unknown_names)
        raise ValueError(
            f"Unknown categories: {unknown_display}. Available categories: {available_names}."
        )

    return selected_categories

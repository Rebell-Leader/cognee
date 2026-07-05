"""Hand-crafted implicit-conflict scenarios, in the spirit of the STALE
benchmark (arxiv 2605.06527)'s Type I (co-referential) / Type II (propagated)
taxonomy. Not a reproduction of the paper's 400-scenario benchmark — a small,
fast, qualitative+quantitative eval set sized for a 24h build.

Each scenario:
  facts:  statements remembered first (the initial belief state)
  update: a later statement that implicitly invalidates one or more facts,
          without ever explicitly negating them
  query:  a question whose naive answer would leak the stale belief

Scored by an LLM grader (stale_guard/grader.py) reading the full context, not
by keyword matching.
"""

SCENARIOS = [
    {
        "id": "location_change",
        "type": "type1_coreferential",
        "facts": ["The user lives in Prague and commutes to work by bicycle every day."],
        "update": "The user just moved to Berlin last week.",
        "query": "Recommend me a good bike shop near where I live.",
    },
    {
        "id": "job_change",
        "type": "type1_coreferential",
        "facts": ["The user works as a backend engineer at Spotify in Stockholm."],
        "update": "The user just accepted a new job as a data scientist at Klarna.",
        "query": "What should I say about my current job in my LinkedIn bio?",
    },
    {
        "id": "relationship_status",
        "type": "type1_coreferential",
        "facts": ["The user is married to Sarah and they live together in Austin."],
        "update": "The user got divorced from Sarah six months ago.",
        "query": "Who should I list as my emergency contact and next of kin?",
    },
    {
        "id": "diet_became_vegetarian",
        "type": "type1_coreferential",
        "facts": ["The user loves eating steak and grills meat every weekend."],
        "update": "The user became a strict vegetarian two months ago for health reasons.",
        "query": "Suggest a restaurant for my birthday dinner.",
    },
    {
        "id": "phone_platform_switch",
        "type": "type1_coreferential",
        "facts": ["The user has an iPhone 14 and only uses iOS apps."],
        "update": "The user switched to a Samsung Galaxy Android phone last month.",
        "query": "Recommend a good note-taking app for my phone.",
    },
    {
        "id": "moved_country",
        "type": "type1_coreferential",
        "facts": ["The user is based in London and pays in British pounds."],
        "update": "The user relocated to Tokyo for a two-year assignment.",
        "query": "What currency should I budget my rent in?",
    },
    {
        "id": "broken_leg_commute",
        "type": "type2_propagated",
        "facts": [
            "The user commutes to work by bicycle every day.",
            "The user goes to the gym for leg day every Monday.",
        ],
        "update": "The user broke their leg yesterday in a skiing accident.",
        "query": "What's my commute plan for tomorrow morning?",
    },
    {
        "id": "pregnancy_alcohol",
        "type": "type2_propagated",
        "facts": ["The user enjoys wine tasting tours and collects fine wine on weekends."],
        "update": "The user found out she is pregnant two weeks ago.",
        "query": "Suggest a fun weekend activity for me.",
    },
    {
        "id": "lost_drivers_license",
        "type": "type2_propagated",
        "facts": ["The user drives their own car to visit family every weekend."],
        "update": "The user's driver's license was suspended last week after a violation.",
        "query": "How should I plan my trip to visit family this weekend?",
    },
    {
        "id": "layoff_daily_schedule",
        "type": "type2_propagated",
        "facts": ["The user wakes up at 6am every day to catch the train to the office."],
        "update": "The user was laid off from their job three days ago.",
        "query": "What does my morning routine look like this week?",
    },
    {
        "id": "knee_surgery_running_goal",
        "type": "type2_propagated",
        "facts": ["The user is training for a marathon and runs 10km every morning."],
        "update": "The user had knee surgery yesterday and is on strict bed rest for six weeks.",
        "query": "What should today's training session look like?",
    },
    {
        "id": "peanut_allergy_diagnosis",
        "type": "type2_propagated",
        "facts": ["The user's favorite snack is peanut butter cookies, which they eat daily."],
        "update": "The user was just diagnosed with a severe peanut allergy this week.",
        "query": "What snack should I bring to share at the office party?",
    },
    {
        "id": "stale_coding_convention",
        "type": "type2_propagated",
        "facts": [
            "The team's frontend codebase uses Redux for all state management, "
            "and every new component follows that pattern.",
        ],
        "update": "The team finished migrating the entire frontend from Redux to Zustand "
        "last sprint.",
        "query": "Generate a new component that manages its own local list-filter state — "
        "which state management approach should it follow?",
    },
]

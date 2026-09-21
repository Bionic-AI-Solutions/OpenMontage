#!/usr/bin/env python3
"""Initialize coffee-world explainer project + research_brief checkpoint."""

from __future__ import annotations

import json
from datetime import date

from lib.checkpoint import PROJECTS_DIR, init_project, write_checkpoint
from schemas.artifacts import validate_artifact


PROJECT_ID = "coffee-world-consumption"
TITLE = "Coffee Around the World"
PIPELINE = "animated-explainer"
PLAYBOOK = "flat-motion-graphics"


def main() -> None:
    project_dir = init_project(
        PROJECT_ID,
        title=TITLE,
        pipeline_type=PIPELINE,
        style_playbook=PLAYBOOK,
    )

    research = {
        "version": "1.0",
        "topic": "Coffee consumption around the world (data-driven explainer)",
        "research_date": date.today().isoformat(),
        "research_summary": (
            "The surprising story is not that Americans drink a lot of coffee — "
            "it is that Northern Europe (especially Finland at ~12 kg/person/year) "
            "drinks 2–3× more per person than the US (~4 kg), while the biggest "
            "producers (Brazil, Vietnam) are not the heaviest drinkers. Global "
            "demand (~180M bags) is currently outrunning supply, making a "
            "per-capita map the cleanest way to shatter coffee stereotypes."
        ),
        "landscape": {
            "existing_content": [
                {
                    "title": "How many people drink coffee in Finland",
                    "url": "https://www.youtube.com/watch?v=rBL7CAWmbLY",
                    "source": "youtube",
                    "angle": "single-country deep dive / culture",
                    "what_it_covers": "Finland's ~12 kg/person ritual, kahvitauko, outdoor brewing",
                    "what_it_misses": "Global ranking context and producer-vs-consumer contrast",
                    "engagement_signal": "Popular explainer-style short on Finnish coffee culture",
                },
                {
                    "title": "Ranked: Which Country Consumes the Most Coffee?",
                    "url": "https://www.visualcapitalist.com/ranked-which-country-consumes-the-most-coffee/",
                    "source": "blog",
                    "angle": "static ranking visualization (cups/day)",
                    "what_it_covers": "Top countries by cups/day (Luxembourg, Finland, Sweden…)",
                    "what_it_misses": "Narrated story arc; producer countries vs drinkers; price shock",
                    "engagement_signal": "Visual Capitalist ranking format — widely shared",
                },
                {
                    "title": "The Top Coffee-Consuming Countries",
                    "url": "https://www.worldatlas.com/society/the-top-coffee-consuming-countries.html",
                    "source": "blog",
                    "angle": "encyclopedia ranking with cultural notes",
                    "what_it_covers": "ICO-style lbs/person rankings + Nordic cultural context",
                    "what_it_misses": "Motion graphics / short-form video; counterintuitive US gap",
                    "engagement_signal": "Long-form reference article",
                },
            ],
            "saturated_angles": [
                "Starbucks / specialty coffee shop culture in the US",
                "How to brew the perfect pour-over",
                "Is coffee good or bad for you?",
                "Single-country Finland coffee obsession (already well covered)",
            ],
            "underserved_gaps": [
                "Producer vs consumer paradox (Brazil grows it; Nordics drink it)",
                "Per-capita map that makes US look modest",
                "Short data-story that explains why Luxembourg rankings can be misleading",
                "2024–25 demand-outpacing-supply as closing punch",
            ],
        },
        "trending": {
            "recent_developments": [
                {
                    "headline": "World coffee consumption ~180M bags while production trails",
                    "url": "https://www.verenastreet.com/blogs/all-about-coffee/coffee-statistics",
                    "date": "2025",
                    "relevance": "Gives urgency: this is not just trivia — the market is tight",
                },
                {
                    "headline": "Arabica futures spiked after Brazilian drought / Vietnam disruptions",
                    "url": "https://www.worldatlas.com/society/the-top-coffee-consuming-countries.html",
                    "date": "2024-2025",
                    "relevance": "Explains why coffee prices feel painful to everyday drinkers",
                },
            ],
            "active_discussions": [
                {
                    "platform": "general",
                    "topic_or_url": "Why do Nordic countries drink so much coffee?",
                    "sentiment": "curiosity + culture envy; people surprised by US ranking",
                    "key_quotes": [
                        "Wait, Italy isn't #1?",
                        "Finland drinks HOW much?",
                    ],
                }
            ],
            "timeliness_window": "evergreen",
        },
        "data_points": [
            {
                "claim": "Finland consumes about 12 kg of coffee per person per year (~3–4 cups/day for adults).",
                "source_url": "https://www.meetlabcoffee.com/post/per-capita-coffee-consumption-in-2024-leading-countries",
                "source_name": "Meet Lab Coffee / common ICO-derived per-capita figures (2024)",
                "credibility": "secondary_source",
                "surprise_factor": "surprising",
                "usable_as": "hook",
            },
            {
                "claim": "The United States is closer to ~4.2 kg per person/year — far below Nordic leaders despite Starbucks ubiquity.",
                "source_url": "https://www.meetlabcoffee.com/post/per-capita-coffee-consumption-in-2024-leading-countries",
                "source_name": "Meet Lab Coffee per-capita table (2024)",
                "credibility": "secondary_source",
                "surprise_factor": "counterintuitive",
                "usable_as": "stat_card",
            },
            {
                "claim": "Norway (~9.9 kg), Iceland (~9 kg), Denmark (~9 kg), Netherlands (~8.4 kg), Sweden (~8.2 kg) fill out the top per-capita tier.",
                "source_url": "https://www.meetlabcoffee.com/post/per-capita-coffee-consumption-in-2024-leading-countries",
                "source_name": "Meet Lab Coffee per-capita table (2024)",
                "credibility": "secondary_source",
                "surprise_factor": "notable",
                "usable_as": "script_anchor",
            },
            {
                "claim": "The world drinks on the order of 2.2–2.3 billion cups of coffee every day.",
                "source_url": "https://www.verenastreet.com/blogs/all-about-coffee/coffee-statistics",
                "source_name": "Verena Street coffee statistics compilation (SCA estimate cited)",
                "credibility": "secondary_source",
                "surprise_factor": "notable",
                "usable_as": "hook",
            },
            {
                "claim": "Global consumption is estimated around 180 million 60-kg bags while production forecasts lag — demand outpaces supply.",
                "source_url": "https://www.verenastreet.com/blogs/all-about-coffee/coffee-statistics",
                "source_name": "ICO / USDA FAS figures as compiled 2025",
                "credibility": "secondary_source",
                "surprise_factor": "notable",
                "usable_as": "closing_punch",
            },
            {
                "claim": "Brazil produces ~40% of world coffee (tens of millions of bags) but ranks mid-pack on per-capita drinking — growers ≠ heaviest drinkers.",
                "source_url": "https://www.verenastreet.com/blogs/all-about-coffee/coffee-statistics",
                "source_name": "USDA FAS production share (2024/25) + per-capita rankings",
                "credibility": "secondary_source",
                "surprise_factor": "counterintuitive",
                "usable_as": "script_anchor",
            },
        ],
        "audience_insights": {
            "common_questions": [
                "Which country drinks the most coffee?",
                "Is it Italy or the US?",
                "Why do Finns drink so much coffee?",
                "Do coffee-growing countries drink their own crop?",
                "How many cups does the world drink per day?",
            ],
            "misconceptions": [
                {
                    "myth": "Italy or the US must top the world because espresso and Starbucks are famous.",
                    "reality": "Per-capita leaders are Nordic/Northern European; US/Italy sit far lower.",
                    "source": "Per-capita rankings (ICO-derived tables)",
                },
                {
                    "myth": "The biggest coffee producers drink the most coffee.",
                    "reality": "Brazil and Vietnam dominate production; Northern Europe dominates per-capita consumption.",
                    "source": "USDA production vs per-capita consumption tables",
                },
            ],
            "knowledge_level": "general_public — knows coffee culture brands, weak on per-capita geography",
        },
        "angles_discovered": [
            {
                "name": "The Map That Humiliates Starbucks",
                "hook": "America feels caffeinated. The data says Finland drinks three times more.",
                "type": "data_driven",
                "why_now": "Per-capita rankings still shock US audiences; Visual Capitalist lists are popular but rarely narrated as a 90s story.",
                "grounded_in": [
                    "Finland ~12 kg vs US ~4.2 kg",
                    "Nordic top-tier cluster",
                ],
            },
            {
                "name": "Growers Don't Drink the Crown",
                "hook": "Brazil grows the world's coffee. Someone else drinks it.",
                "type": "contrarian",
                "why_now": "Producer-vs-consumer paradox is underserved in short video; pairs cleanly with a split map.",
                "grounded_in": [
                    "Brazil ~40% of production",
                    "Nordic per-capita leadership",
                ],
            },
            {
                "name": "Two Billion Cups Before Lunch",
                "hook": "Humanity drinks more than two billion cups of coffee every day — here's who owns the habit.",
                "type": "narrative",
                "why_now": "Scale hook + country race + closing supply crunch lands as a complete mini-doc.",
                "grounded_in": [
                    "2.2–2.3B cups/day",
                    "Demand outpacing supply ~180M bags",
                ],
            },
        ],
        "sources": [
            {
                "title": "Per Capita Coffee Consumption in 2024: Leading Countries",
                "url": "https://www.meetlabcoffee.com/post/per-capita-coffee-consumption-in-2024-leading-countries",
                "used_for": "data_points per-capita rankings",
                "reliability": "secondary",
            },
            {
                "title": "Coffee Consumption Statistics 2026 - Global & U.S. Data",
                "url": "https://www.verenastreet.com/blogs/all-about-coffee/coffee-statistics",
                "used_for": "global cups/day, production vs consumption, Brazil share",
                "reliability": "secondary",
            },
            {
                "title": "The Top Coffee-Consuming Countries",
                "url": "https://www.worldatlas.com/society/the-top-coffee-consuming-countries.html",
                "used_for": "landscape + cultural context + price shock",
                "reliability": "secondary",
            },
            {
                "title": "Ranked: Which Country Consumes the Most Coffee?",
                "url": "https://www.visualcapitalist.com/ranked-which-country-consumes-the-most-coffee/",
                "used_for": "landscape existing_content + cups/day framing",
                "reliability": "secondary",
            },
            {
                "title": "How many people drink coffee in Finland",
                "url": "https://www.youtube.com/watch?v=rBL7CAWmbLY",
                "used_for": "landscape existing_content Finland deep-dive",
                "reliability": "anecdotal",
            },
        ],
    }

    validate_artifact("research_brief", research)

    art_path = project_dir / "artifacts" / "research_brief.json"
    art_path.write_text(json.dumps(research, indent=2))

    write_checkpoint(
        PROJECTS_DIR,
        PROJECT_ID,
        "research",
        "completed",
        {"research_brief": research},
        pipeline_type=PIPELINE,
        style_playbook=PLAYBOOK,
        human_approved=True,
        metadata={
            "notes": "Research complete — awaiting proposal approval",
            "artifact_path": "artifacts/research_brief.json",
        },
    )
    print(f"OK project={project_dir}")
    print(f"board=https://om.baisoln.com/p/{PROJECT_ID}")


if __name__ == "__main__":
    main()

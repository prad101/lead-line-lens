"""Plain-language next steps for a resident. Not medical or legal advice.

Every health claim has a source URL. A prediction never lowers urgency: Unknown
is always treated as possibly lead until verified.
"""

from __future__ import annotations

from dataclasses import dataclass

from lll.predict import TREAT_AS_LEAD_MESSAGE

LOOKUP_BUTTON = "Look up this address"
PLAN_BUTTON = "See what I can do today"
LETTER_BUTTON = "Get a letter you can send"
PRIMARY_CLICKS = (LOOKUP_BUTTON, PLAN_BUTTON, LETTER_BUTTON)

SURVEY_QUESTIONS = (
    "Does a child under 6 or a pregnant person live here?",
    "Do you use a filter certified to reduce lead?",
    "Did the city tell you this line may be lead?",
    "Do you own or rent this home?",
    "Have you tested this tap for lead?",
)

LINKS = {
    "epa_lead": (
        "U.S. EPA",
        "https://www.epa.gov/ground-water-and-drinking-water/"
        "basic-information-about-lead-drinking-water",
    ),
    "epa_filter": (
        "U.S. EPA",
        "https://www.epa.gov/water-research/"
        "consumer-tool-identifying-point-use-and-pitcher-filters-certified-reduce-lead",
    ),
    "test_kit": ("City of Chicago", "https://www.chicagowaterquality.org/"),
    "city_lookup": ("City of Chicago", "https://sli.chicagowaterquality.org/"),
    "equity": (
        "Lead Safe Chicago",
        "https://www.leadsafechicago.org/equity-lead-service-line-replacement-program",
    ),
    "cdph": (
        "Chicago Department of Public Health",
        "https://www.chicago.gov/lead",
    ),
}

_KNOWN = ("Lead", "GRR", "Non-Lead")
_NEEDS_CARE = ("Lead", "GRR", "Unknown")


@dataclass(frozen=True)
class Advice:
    text: str
    source_label: str | None = None
    source_url: str | None = None
    health: bool = False


def _item(text: str, key: str, *, health: bool = False) -> Advice:
    label, url = LINKS[key]
    return Advice(text=text, source_label=label, source_url=url, health=health)


def status_plain(material: str | None) -> str:
    """One short label for a recorded material."""
    m = material or "Unknown"
    if m == "Lead":
        return "Lead"
    if m == "GRR":
        return "Galvanized (must be replaced)"
    if m == "Non-Lead":
        return "Not lead in city records"
    return "Unknown — possibly lead until checked"


def plan_for(
    *,
    line_status: str,
    utility_side: str,
    customer_side: str,
    child_or_pregnancy: bool,
    has_filter: str,
    notified: str,
    tenure: str,
    tested: str,
) -> list[Advice]:
    """Personalized next steps. Unknown never reads as safe."""
    status = line_status if line_status in _KNOWN else "Unknown"
    if customer_side == "Unknown" or utility_side == "Unknown":
        status = "Unknown" if status == "Non-Lead" else status
    items: list[Advice] = []

    if status == "Unknown" or customer_side == "Unknown" or utility_side == "Unknown":
        items.append(Advice(TREAT_AS_LEAD_MESSAGE))
        items.append(Advice(
            "City records do not say what this pipe is made of. "
            "A model can guess. A guess is not a check."
        ))
    elif (status in ("Lead", "GRR") or customer_side in ("Lead", "GRR")
          or utility_side in ("Lead", "GRR")):
        items.append(Advice(
            "City records list this line as lead or galvanized. Plan to replace it."
        ))
    else:
        items.append(Advice(
            "City records list this line as not lead. Records can be wrong. "
            "You can still ask the city to check."
        ))

    care = status in _NEEDS_CARE or customer_side in _NEEDS_CARE or utility_side in _NEEDS_CARE
    if care or child_or_pregnancy:
        items.append(_item(
            "Lead is most harmful to young children and pregnant people.",
            "epa_lead", health=True,
        ))
        items.append(_item(
            "Do not boil water to remove lead. Boiling does not take lead out.",
            "epa_lead", health=True,
        ))
        if has_filter != "yes":
            items.append(_item(
                "Use a filter certified to reduce lead for drinking and cooking, "
                "or use bottled water.",
                "epa_filter", health=True,
            ))
        else:
            items.append(_item(
                "Keep using your lead-reducing filter for drinking and cooking. "
                "A filter does not replace a lead pipe.",
                "epa_filter", health=True,
            ))

    if tested != "yes":
        items.append(_item(
            "Get a free water test kit from the city. Call 311 or visit the city water site.",
            "test_kit",
        ))
    else:
        items.append(_item(
            "A tap test is useful. It still does not replace a check of the pipe itself.",
            "test_kit",
        ))

    items.append(_item(
        "You can also look up this address on the city's own service line map.",
        "city_lookup",
    ))

    if tenure == "own" and care:
        items.append(_item(
            "Homeowners with lower incomes may qualify for a free pipe replacement.",
            "equity",
        ))
    if tenure == "rent":
        items.append(Advice(
            "If you rent, send the letter and keep a copy. Ask the owner to help "
            "with a replacement."
        ))
    if notified == "no" and care:
        items.append(Advice(
            "Ask the city to tell you in writing that this line may be lead."
        ))

    items.append(_item(
        "This page is not medical advice. For health questions, talk to a doctor "
        "or the Chicago Department of Public Health.",
        "cdph", health=True,
    ))
    return items


def markdown(item: Advice) -> str:
    """Render one step with its source link when present."""
    if item.source_url and item.source_label:
        return f"{item.text} ([{item.source_label}]({item.source_url}))"
    return item.text


def plan_text(items: list[Advice]) -> str:
    return " ".join(i.text for i in items)

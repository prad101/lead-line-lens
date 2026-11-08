"""Lead Line Lens API.

Privacy: addresses, survey answers, and letters are processed in memory only.
Nothing from a request body or query string is written to disk, a database, or logs.
"""

from fastapi import FastAPI

from api.routers import area, letter, lookup, predict, scorecard, utility
from lll import METHODOLOGY_URL, MODEL_CARD_URL, __version__

app = FastAPI(
    title="Lead Line Lens API",
    version=__version__,
    description=(
        "Decode a water utility's lead service line inventory. "
        f"Methodology: {METHODOLOGY_URL} . Model card: {MODEL_CARD_URL} . "
        "No address, survey response, or letter is stored or logged."
    ),
)

app.include_router(lookup.router)
app.include_router(predict.router)
app.include_router(area.router)
app.include_router(letter.router)
app.include_router(scorecard.router)
app.include_router(utility.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness. Does not load the inventory; missing data is a 503 on the data routes."""
    return {"status": "ok", "version": __version__}

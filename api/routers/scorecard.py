from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import Response

router = APIRouter(tags=["scorecard"])


@router.get(
    "/scorecard/ward/{ward}.pdf",
    summary="One-page ward scorecard PDF",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def ward_scorecard(ward: int = Path(..., ge=1, le=50)):
    """Rendered on request from the latest master table and disparity report."""
    from lll.scorecard import ward_pdf

    try:
        pdf = ward_pdf(ward)
    except FileNotFoundError as err:
        raise HTTPException(status_code=503, detail=str(err)) from None
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="ward_{ward:02d}_scorecard.pdf"'},
    )

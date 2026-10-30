from fastapi import HTTPException


def not_implemented(gate: str) -> HTTPException:
    return HTTPException(status_code=501, detail=f"Not implemented yet ({gate}).")

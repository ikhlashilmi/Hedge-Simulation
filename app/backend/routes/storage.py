from fastapi import APIRouter, HTTPException
import json
import logging
import re
from pathlib import Path
from pydantic import BaseModel

from app.backend.models.schemas import ErrorResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/storage")

_SAFE_JSON_FILENAME_RE = re.compile(r"^[A-Za-z0-9_-][\w.\-]*\.json$")


class SaveJsonRequest(BaseModel):
    filename: str
    data: dict


@router.post(
    path="/save-json",
    responses={
        200: {"description": "File saved successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def save_json_file(request: SaveJsonRequest):
    """Save JSON data to the project's /outputs directory."""
    safe_name = Path(request.filename).name
    if (
        not request.filename
        or safe_name != request.filename
        or not _SAFE_JSON_FILENAME_RE.match(safe_name)
    ):
        raise HTTPException(status_code=400, detail="Invalid filename")

    try:
        # Create outputs directory if it doesn't exist
        project_root = Path(__file__).parent.parent.parent.parent  # Navigate to project root
        outputs_dir = (project_root / "outputs").resolve()
        outputs_dir.mkdir(exist_ok=True)

        # Construct and verify resolved file path stays inside outputs_dir
        file_path = (outputs_dir / safe_name).resolve()
        if not file_path.is_relative_to(outputs_dir):
            raise HTTPException(status_code=400, detail="Invalid filename")

        # Save JSON data to file
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(request.data, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "message": f"File saved successfully as {safe_name}",
            "filename": safe_name,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to save JSON file")
        raise HTTPException(status_code=500, detail="Failed to save file")
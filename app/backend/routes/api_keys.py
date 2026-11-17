import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

from app.backend.database import get_db
from app.backend.repositories.api_key_repository import ApiKeyRepository
from app.backend.services.crypto import decrypt_secret, mask_secret
from app.backend.models.schemas import (
    ApiKeyCreateRequest,
    ApiKeyUpdateRequest,
    ApiKeyResponse,
    ApiKeySummaryResponse,
    ApiKeyBulkUpdateRequest,
    ErrorResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api-keys", tags=["api-keys"])


def _to_masked_response(api_key) -> ApiKeyResponse:
    plain = decrypt_secret(api_key.key_value)
    return ApiKeyResponse(
        id=api_key.id,
        provider=api_key.provider,
        key_value=mask_secret(plain),
        is_active=api_key.is_active,
        description=api_key.description,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at,
        last_used=api_key.last_used,
    )


@router.post(
    "/",
    response_model=ApiKeyResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def create_or_update_api_key(request: ApiKeyCreateRequest, db: Session = Depends(get_db)):
    """Create a new API key or update existing one"""
    try:
        repo = ApiKeyRepository(db)
        api_key = repo.create_or_update_api_key(
            provider=request.provider,
            key_value=request.key_value,
            description=request.description,
            is_active=request.is_active
        )
        return _to_masked_response(api_key)
    except Exception:
        logger.exception("Failed to create/update API key")
        raise HTTPException(status_code=500, detail="Failed to create/update API key")


@router.get(
    "/",
    response_model=List[ApiKeySummaryResponse],
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def get_api_keys(include_inactive: bool = False, db: Session = Depends(get_db)):
    """Get all API keys (without actual key values for security)"""
    try:
        repo = ApiKeyRepository(db)
        api_keys = repo.get_all_api_keys(include_inactive=include_inactive)
        return [ApiKeySummaryResponse.model_validate(key) for key in api_keys]
    except Exception:
        logger.exception("Failed to retrieve API keys")
        raise HTTPException(status_code=500, detail="Failed to retrieve API keys")


@router.get(
    "/{provider}",
    response_model=ApiKeyResponse,
    responses={
        404: {"model": ErrorResponse, "description": "API key not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def get_api_key(provider: str, db: Session = Depends(get_db)):
    """Get a specific API key by provider (masked for security)"""
    try:
        repo = ApiKeyRepository(db)
        api_key = repo.get_api_key_by_provider(provider)
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        return _to_masked_response(api_key)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to retrieve API key")
        raise HTTPException(status_code=500, detail="Failed to retrieve API key")


@router.put(
    "/{provider}",
    response_model=ApiKeyResponse,
    responses={
        404: {"model": ErrorResponse, "description": "API key not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def update_api_key(provider: str, request: ApiKeyUpdateRequest, db: Session = Depends(get_db)):
    """Update an existing API key"""
    try:
        repo = ApiKeyRepository(db)
        api_key = repo.update_api_key(
            provider=provider,
            key_value=request.key_value,
            description=request.description,
            is_active=request.is_active
        )
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        return _to_masked_response(api_key)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update API key")
        raise HTTPException(status_code=500, detail="Failed to update API key")


@router.delete(
    "/{provider}",
    responses={
        204: {"description": "API key deleted successfully"},
        404: {"model": ErrorResponse, "description": "API key not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def delete_api_key(provider: str, db: Session = Depends(get_db)):
    """Delete an API key"""
    try:
        repo = ApiKeyRepository(db)
        success = repo.delete_api_key(provider)
        if not success:
            raise HTTPException(status_code=404, detail="API key not found")
        return {"message": "API key deleted successfully"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete API key")
        raise HTTPException(status_code=500, detail="Failed to delete API key")


@router.patch(
    "/{provider}/deactivate",
    response_model=ApiKeySummaryResponse,
    responses={
        404: {"model": ErrorResponse, "description": "API key not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def deactivate_api_key(provider: str, db: Session = Depends(get_db)):
    """Deactivate an API key without deleting it"""
    try:
        repo = ApiKeyRepository(db)
        success = repo.deactivate_api_key(provider)
        if not success:
            raise HTTPException(status_code=404, detail="API key not found")

        # Return the updated key (must include inactive since it was just deactivated)
        api_key = repo.get_api_key_by_provider(provider, include_inactive=True)
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        return ApiKeySummaryResponse.model_validate(api_key)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to deactivate API key")
        raise HTTPException(status_code=500, detail="Failed to deactivate API key")


@router.post(
    "/bulk",
    response_model=List[ApiKeyResponse],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def bulk_update_api_keys(request: ApiKeyBulkUpdateRequest, db: Session = Depends(get_db)):
    """Bulk create or update multiple API keys"""
    try:
        repo = ApiKeyRepository(db)
        api_keys_data = [
            {
                'provider': key.provider,
                'key_value': key.key_value,
                'description': key.description,
                'is_active': key.is_active
            }
            for key in request.api_keys
        ]
        api_keys = repo.bulk_create_or_update(api_keys_data)
        return [_to_masked_response(key) for key in api_keys]
    except Exception:
        logger.exception("Failed to bulk update API keys")
        raise HTTPException(status_code=500, detail="Failed to bulk update API keys")


@router.patch(
    "/{provider}/last-used",
    responses={
        200: {"description": "Last used timestamp updated"},
        404: {"model": ErrorResponse, "description": "API key not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def update_last_used(provider: str, db: Session = Depends(get_db)):
    """Update the last used timestamp for an API key"""
    try:
        repo = ApiKeyRepository(db)
        success = repo.update_last_used(provider)
        if not success:
            raise HTTPException(status_code=404, detail="API key not found")
        return {"message": "Last used timestamp updated"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update last used timestamp")
        raise HTTPException(status_code=500, detail="Failed to update last used timestamp")
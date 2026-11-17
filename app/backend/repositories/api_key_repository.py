from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from app.backend.database.models import ApiKey
from app.backend.services.crypto import decrypt_secret, encrypt_secret, mask_secret


class ApiKeyRepository:
    """Repository for API key database operations"""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _is_masked_placeholder(incoming_value: str, existing_plain: str) -> bool:
        return incoming_value == "****" or (bool(existing_plain) and incoming_value == mask_secret(existing_plain))

    def create_or_update_api_key(
        self,
        provider: str,
        key_value: str,
        description: str = None,
        is_active: bool = True
    ) -> ApiKey:
        """Create a new API key or update existing one"""
        existing_key = self.db.query(ApiKey).filter(ApiKey.provider == provider).first()

        if existing_key:
            existing_plain = decrypt_secret(existing_key.key_value)
            if self._is_masked_placeholder(key_value, existing_plain):
                # Preserve existing secret and ensure legacy plaintext rows are upgraded
                existing_key.key_value = encrypt_secret(existing_plain)
            else:
                existing_key.key_value = encrypt_secret(key_value)
            existing_key.description = description
            existing_key.is_active = is_active
            existing_key.updated_at = func.now()
            self.db.commit()
            self.db.refresh(existing_key)
            return existing_key
        else:
            api_key = ApiKey(
                provider=provider,
                key_value=encrypt_secret(key_value),
                description=description,
                is_active=is_active
            )
            self.db.add(api_key)
            self.db.commit()
            self.db.refresh(api_key)
            return api_key

    def get_api_key_by_provider(self, provider: str, include_inactive: bool = False) -> Optional[ApiKey]:
        """Get API key by provider name"""
        query = self.db.query(ApiKey).filter(ApiKey.provider == provider)
        if not include_inactive:
            query = query.filter(ApiKey.is_active == True)
        return query.first()

    def get_all_api_keys(self, include_inactive: bool = False) -> List[ApiKey]:
        """Get all API keys"""
        query = self.db.query(ApiKey)
        if not include_inactive:
            query = query.filter(ApiKey.is_active == True)
        return query.order_by(ApiKey.provider).all()

    def update_api_key(
        self,
        provider: str,
        key_value: str = None,
        description: str = None,
        is_active: bool = None
    ) -> Optional[ApiKey]:
        """Update an existing API key"""
        api_key = self.db.query(ApiKey).filter(ApiKey.provider == provider).first()
        if not api_key:
            return None

        if key_value is not None:
            existing_plain = decrypt_secret(api_key.key_value)
            if self._is_masked_placeholder(key_value, existing_plain):
                api_key.key_value = encrypt_secret(existing_plain)
            else:
                api_key.key_value = encrypt_secret(key_value)
        if description is not None:
            api_key.description = description
        if is_active is not None:
            api_key.is_active = is_active

        api_key.updated_at = func.now()
        self.db.commit()
        self.db.refresh(api_key)
        return api_key

    def delete_api_key(self, provider: str) -> bool:
        """Delete an API key by provider"""
        api_key = self.db.query(ApiKey).filter(ApiKey.provider == provider).first()
        if not api_key:
            return False
        
        self.db.delete(api_key)
        self.db.commit()
        return True

    def deactivate_api_key(self, provider: str) -> bool:
        """Deactivate an API key instead of deleting it"""
        api_key = self.db.query(ApiKey).filter(ApiKey.provider == provider).first()
        if not api_key:
            return False
        
        api_key.is_active = False
        api_key.updated_at = func.now()
        self.db.commit()
        return True

    def update_last_used(self, provider: str) -> bool:
        """Update the last_used timestamp for an API key"""
        api_key = self.db.query(ApiKey).filter(
            ApiKey.provider == provider,
            ApiKey.is_active == True
        ).first()
        if not api_key:
            return False
        
        api_key.last_used = func.now()
        self.db.commit()
        return True

    def bulk_create_or_update(self, api_keys_data: List[dict]) -> List[ApiKey]:
        """Bulk create or update multiple API keys"""
        results = []
        for data in api_keys_data:
            api_key = self.create_or_update_api_key(
                provider=data['provider'],
                key_value=data['key_value'],
                description=data.get('description'),
                is_active=data.get('is_active', True)
            )
            results.append(api_key)
        return results 
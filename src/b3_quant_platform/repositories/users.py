from __future__ import annotations

from sqlalchemy import select

from b3_quant_platform.models.entities import User
from b3_quant_platform.models.enums import UserRole
from b3_quant_platform.repositories.base import SQLAlchemyRepository


class UserRepository(SQLAlchemyRepository[User]):
    model = User

    def create_user(
        self,
        *,
        email: str,
        full_name: str | None = None,
        external_auth_id: str | None = None,
        role: UserRole = UserRole.ANALYST,
    ) -> User:
        user = User(
            email=email,
            full_name=full_name,
            external_auth_id=external_auth_id,
            role=role,
            timezone_name="UTC",
            is_active=True,
            preferences_json={},
        )
        return self.add(user)

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))

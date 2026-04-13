from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import PromptVersion


class PromptService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ensure_default_prompt(self) -> PromptVersion:
        active_prompt = await self.get_active_prompt()
        if active_prompt:
            return active_prompt

        prompt = PromptVersion(
            version=settings.PROMPT_VERSION,
            prompt_text=settings.DEFAULT_PROMPT_TEXT,
            is_active=True,
        )
        self.db.add(prompt)
        await self.db.flush()
        return prompt

    async def get_active_prompt(self) -> PromptVersion | None:
        result = await self.db.execute(select(PromptVersion).where(PromptVersion.is_active.is_(True)))
        return result.scalar_one_or_none()

    async def list_versions(self) -> list[PromptVersion]:
        result = await self.db.execute(select(PromptVersion).order_by(PromptVersion.created_at.desc()))
        return list(result.scalars().all())

    async def create_version(self, version: str, text: str) -> PromptVersion:
        await self.db.execute(update(PromptVersion).values(is_active=False))
        prompt = PromptVersion(version=version, prompt_text=text, is_active=True)
        self.db.add(prompt)
        await self.db.flush()
        return prompt

    async def get_by_id(self, prompt_id: int) -> PromptVersion | None:
        result = await self.db.execute(select(PromptVersion).where(PromptVersion.id == prompt_id))
        return result.scalar_one_or_none()

    async def update_version(self, prompt_id: int, version: str, text: str) -> PromptVersion | None:
        prompt = await self.get_by_id(prompt_id)
        if not prompt:
            return None
        prompt.version = version
        prompt.prompt_text = text
        await self.db.flush()
        return prompt

    async def activate_version(self, prompt_id: int) -> PromptVersion | None:
        prompt = await self.get_by_id(prompt_id)
        if not prompt:
            return None
        await self.db.execute(update(PromptVersion).values(is_active=False))
        prompt.is_active = True
        await self.db.flush()
        return prompt

"""Message routing for the "📩 تماس با مدیریت" (contact admin) feature.

Every message relayed into an admin's chat gets a row here keyed by where it
landed. When an admin replies to one of those copies, the same key looks up
which user the reply belongs to — see ``handlers/contact_admin.py``.
"""

from __future__ import annotations

from sqlalchemy import select

from database.connection import get_db_session
from database.models import SupportMessage, User


async def record_relay(*, user_id: int, admin_chat_id: int, admin_message_id: int) -> None:
    """Remember that ``admin_message_id`` (in ``admin_chat_id``) belongs to ``user_id``."""
    async with get_db_session() as session:
        session.add(
            SupportMessage(
                user_id=user_id,
                admin_chat_id=admin_chat_id,
                admin_message_id=admin_message_id,
            )
        )


async def find_user_for_reply(*, admin_chat_id: int, admin_message_id: int) -> User | None:
    """Return the user a reply-to'd admin message belongs to, if tracked."""
    async with get_db_session() as session:
        support_msg = await session.scalar(
            select(SupportMessage).where(
                SupportMessage.admin_chat_id == admin_chat_id,
                SupportMessage.admin_message_id == admin_message_id,
            )
        )
        if support_msg is None:
            return None
        return await session.scalar(select(User).where(User.id == support_msg.user_id))

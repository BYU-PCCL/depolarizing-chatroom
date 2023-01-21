import os
import random
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, List, Optional

from fastapi_async_sqlalchemy import db
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from . import models
from .database import Base
from .models import UserPosition


class DataAccess:
    @asynccontextmanager
    async def commit_after(self) -> None:
        try:
            yield
        finally:
            await db.session.commit()

    @property
    def session(self) -> AsyncSession:
        return db.session

    def _check_explicit_transaction(self) -> None:
        pass
        # if not _in_explicit_transaction.get():
        #     raise RuntimeError(
        #         "This method must be called within an explicit transaction"
        #     )

    def add(self, obj: Base) -> None:
        db.session.add(obj)

    def create_chatroom(self) -> models.Chatroom:
        self.add(
            chatroom := models.Chatroom(swap_view_messages=random.choice([True, False]))
        )
        return chatroom

    async def message(self, id) -> Optional[models.Message]:
        self._check_explicit_transaction()
        return await db.session.get(
            models.Message,
            id,
            options=[
                selectinload(models.Message.rephrasings),
                selectinload(models.Message.user),
                selectinload(models.Message.chatroom),
                selectinload(models.Message.accepted_rephrasing),
            ],
        )

    async def chatroom_messages(
        self,
        chatroom: models.Chatroom,
        select_users: bool = False,
        select_rephrasings: bool = False,
    ) -> List[models.Message]:
        self._check_explicit_transaction()
        statement = (
            select(models.Message)
            .filter_by(chatroom_id=chatroom.id)
            .order_by(models.Message.send_time.asc())
            .options(selectinload(models.Message.accepted_rephrasing))
        )
        if select_users:
            statement = statement.options(selectinload(models.Message.user))
        if select_rephrasings:
            statement = statement.options(selectinload(models.Message.rephrasings))
        response = await db.session.execute(statement)
        messages = response.scalars().all()
        # Swap first two messages if chatroom.swap_view_messages is true
        if chatroom.swap_view_messages and len(messages) >= 2:
            messages[0], messages[1] = (
                messages[1],
                messages[0],
            )
        return messages

    def add_message(self, chatroom_id, sender_id, message_body) -> models.Message:
        self.add(
            message := models.Message(
                chatroom_id=chatroom_id,
                sender_id=sender_id,
                body=message_body,
                send_time=datetime.now(),
            )
        )
        return message

    async def rephrasing(self, id) -> Optional[models.Rephrasing]:
        self._check_explicit_transaction()
        return await self.session.get(models.Rephrasing, id)

    def add_rephrasing(self, message_id, body, strategy) -> models.Rephrasing:
        self.add(
            rephrasing := models.Rephrasing(
                message_id=message_id, body=body, strategy=strategy
            )
        )
        return rephrasing

    async def user(self, id) -> Optional[models.User]:
        self._check_explicit_transaction()
        return await db.session.get(
            models.User,
            id,
            options=[
                # I don't know if it's a good practice to use selectinload here, but we
                # use these attributes all over the place and they're not particularly
                # large, so I think it's fine.
                selectinload(models.User.chatroom),
                selectinload(models.User.messages),
            ],
        )

    async def users_in_waiting_room(
        self,
        *,
        position: UserPosition = None,
        filter_ids: List[int] = None,
        matched: bool = None,
    ) -> List[models.User]:
        self._check_explicit_transaction()
        user_query = select(models.User)
        filters = [models.User.waiting_session_id.isnot(None)]

        # TODO: Is there not a more elegant way to do this?
        if matched is not None:
            filters.append(
                models.User.found_match_time.is_not(None)
                if matched
                else models.User.found_match_time.is_(None)
            )
        if filter_ids:
            filters.append(models.User.id.in_(filter_ids))
        if position:
            filters.append(models.User.position == position)

        users = await db.session.execute(
            user_query.where(and_(*filters)).order_by(
                models.User.started_waiting_time.asc()
            )
        )
        return users.scalars().all()

    async def random_user_to_match_with(
        self, user: models.User
    ) -> Optional[models.User]:
        self._check_explicit_transaction()
        user_query = (
            select(models.User)
            .filter(
                models.User.id != user.id,
                models.User.waiting_session_id.isnot(None),
                models.User.found_match_time.is_(None),
                models.User.position == user.match_with,
            )
            .order_by(models.User.started_waiting_time.asc())
        )
        user = await db.session.execute(user_query)
        results = user.scalars().all()
        if not results:
            return None
        return random.choice(results)

    async def users_in_chatroom(
        self, *, position: UserPosition = None, filter_ids: List[int] = None
    ) -> List[models.User]:
        self._check_explicit_transaction()
        user_query = select(models.User)
        filters = [models.User.chatroom_session_id.isnot(None)]

        if filter_ids:
            filters.append(models.User.id.in_(filter_ids))
        if position:
            filters.append(models.User.position == position)

        users = await db.session.execute(user_query.where(and_(*filters)))
        return users.scalars().all()

    async def other_user_in_chatroom(
        self, chatroom_id, user_id
    ) -> Optional[models.User]:
        self._check_explicit_transaction()
        user = await db.session.execute(
            select(models.User)
            .options(
                selectinload(models.User.chatroom), selectinload(models.User.messages)
            )
            .filter_by(chatroom_id=chatroom_id)
            .filter(models.User.id != user_id)
        )
        return user.scalar_one_or_none()

    async def user_by_response_id(self, response_id) -> Optional[models.User]:
        self._check_explicit_transaction()
        user = await db.session.execute(
            select(models.User)
            .options(
                selectinload(models.User.chatroom), selectinload(models.User.messages)
            )
            .filter_by(response_id=response_id)
        )
        return user.scalar_one_or_none()

    async def process_login(self, response_id) -> Optional[models.User]:
        self._check_explicit_transaction()
        # TODO: This isn't really that useful other than for providing an API
        return await self.user_by_response_id(response_id)

    async def process_signup(
        self, response_id, position: UserPosition
    ) -> Optional[models.User]:
        self._check_explicit_transaction()
        if await self.user_by_response_id(response_id):
            return None

        user = models.User(response_id=response_id, position=position)

        self.add(user)

        return user

    def save_event(
        self, user_id: int, event: str, *, time: datetime = None, data: Any = None
    ) -> models.UserEvent:
        self.add(
            event := models.UserEvent(
                user_id=user_id,
                event_type=event,
                event_time=time if time else datetime.now(),
                event_data=data,
            )
        )
        return event


async def build_prod_database(force=False) -> None:
    """
    Build production database
    """
    SQLALCHEMY_DATABASE_URL = os.getenv("DB_URI") or "sqlite+aiosqlite:///"
    engine = create_async_engine(
        SQLALCHEMY_DATABASE_URL,
        future=True,
        echo=True
    )
    async with engine.begin() as connection:
        await connection.run_sync(models.Base.metadata.create_all)


# Using the magic of contextvars
access: DataAccess = DataAccess()

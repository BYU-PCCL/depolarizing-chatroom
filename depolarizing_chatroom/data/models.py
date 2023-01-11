import enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

from ..constants import NO_CHAT_URL, POST_CHAT_URL
from .database import Base


class MatchedUser(Base):
    __tablename__ = "matched_users"

    id = Column(Integer, primary_key=True)


class Chatroom(Base):
    __tablename__ = "chatrooms"

    id = Column(Integer, primary_key=True)
    limit_reached = Column(Boolean, default=False)
    error = Column(Boolean, default=False)
    # This is a really hacky way of making the initial view messages show up in a random
    # order
    swap_view_messages = Column(Boolean, default=False)

    # Relationships (one-to-many with users, one-to-many with messages)
    users = relationship("User", back_populates="chatroom")
    messages = relationship("Message", back_populates="chatroom")


class Rephrasing(Base):
    __tablename__ = "rephrasings"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id"))
    body = Column(Text, nullable=False)
    edited_body = Column(Text)
    strategy = Column(Text)

    # Relationship (many-to-one with messages)
    message = relationship(
        "Message",
        back_populates="rephrasings",
        foreign_keys=message_id,
        post_update=True,
    )

    @property
    def selected_body(self) -> str:
        return self.edited_body or self.body


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    chatroom_id = Column(Integer, ForeignKey("chatrooms.id"))
    sender_id = Column(Integer, ForeignKey("users.id"))
    body = Column(Text, nullable=False)
    # This should be nullable
    edited_body = Column(Text)
    send_time = Column(DateTime, nullable=False)
    accepted_rephrasing_id = Column(Integer, ForeignKey("rephrasings.id"))

    # Relationships (one-to-many with rephrasings, many-to-one with chatroom,
    # many-to-one with user)
    rephrasings = relationship(
        # We have to specify foreign_keys here because accepted_rephrasing_id makes
        # the relationship ambiguous—SQLAlchemy needs some help.
        "Rephrasing",
        back_populates="message",
        foreign_keys=Rephrasing.message_id,
        cascade="all, delete-orphan",
        post_update=True,
    )
    accepted_rephrasing = relationship(
        "Rephrasing", foreign_keys=accepted_rephrasing_id
    )
    chatroom = relationship("Chatroom", back_populates="messages")
    user = relationship("User", back_populates="messages")

    @property
    def selected_body(self) -> str:
        if not (rephrasing := self.accepted_rephrasing):
            return self.edited_body or self.body

        return rephrasing.selected_body


class UserPosition(str, enum.Enum):
    OPPOSE = "oppose"
    SUPPORT = "support"


class UserTreatment(int, enum.Enum):
    TREATED = 1
    UNTREATED = 2
    CONTROL = 3

    @property
    def match_with(self) -> "UserTreatment":
        if self is UserTreatment.TREATED:
            return UserTreatment.UNTREATED
        if self is UserTreatment.UNTREATED:
            return UserTreatment.TREATED
        return self


class UserEvent(Base):
    __tablename__ = "user_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_type = Column(String, nullable=False)
    event_time = Column(DateTime, nullable=False)
    event_data = Column(JSON)

    # Relationships (many-to-one with users)
    user = relationship("User", back_populates="events")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    response_id = Column(String(320), nullable=False)
    chatroom_id = Column(Integer, ForeignKey("chatrooms.id"))

    # Short message where user is asked to explain their position
    view = Column(String)

    # Positions:
    # UserPosition.SUPPORT ("support"): Supports stricter gun laws
    # UserPosition.OPPOSE ("oppose"): Opposes stricter gun laws
    position = Column(Enum(UserPosition), nullable=False)
    # Treatment key:
    # 1: Supports stricter gun laws, treated with GPT-3. Matched with 5.
    # 2: Supports stricter gun laws, talks to person treated with GPT-3. Matched with 4.
    # 3: Supports stricter gun laws, untreated conversation. Matched with 6.
    # 4: Opposes stricter gun laws, treated with GPT-3. Matched with 2.
    # 5: Opposes stricter gun laws, talks to person treated with GPT-3. Matched with 1.
    # 6: Opposes stricter gun laws, untreated conversation. Matched with 3.
    treatment = Column(Enum(UserTreatment))

    # Waiting room
    started_waiting_time = Column(DateTime)
    finished_waiting_time = Column(DateTime)
    found_match_time = Column(DateTime)
    waiting_session_id = Column(String)
    # Will always be false for untreated users
    seen_tutorial = Column(Boolean, default=False)
    # Optimistic concurrency control for waiting room using version ID
    match_version = Column(String(32), default="", nullable=False)

    # Chatroom
    # Measured from the first time that a user enters /chatroom with a valid chatroom
    started_chat_time = Column(DateTime)
    finished_chat_time = Column(DateTime)
    chatroom_session_id = Column(String)
    # Reason provided by user for leaving chat early
    leave_reason = Column(Text)

    # Relationships (many-to-one with chatrooms, one-to-many with messages, one-to-many
    # with events)
    chatroom = relationship("Chatroom", back_populates="users")
    messages = relationship(
        "Message", back_populates="user", order_by=Message.send_time.desc
    )
    events = relationship(
        "UserEvent", back_populates="user", order_by=UserEvent.event_time.desc
    )

    @property
    def receives_rephrasings(self) -> bool:
        return self.treatment is UserTreatment.TREATED

    @property
    def in_control_conversation(self) -> bool:
        return self.treatment is UserTreatment.CONTROL

    @property
    def match_with(self) -> UserPosition:
        return (
            UserPosition.SUPPORT
            if self.position == UserPosition.OPPOSE
            else UserPosition.OPPOSE
        )

    @property
    def treatment_code(self) -> Optional[int]:
        if not self.treatment:
            return None
        return self.treatment.value + (
            0 if self.position is UserPosition.SUPPORT else 3
        )

    @property
    def needs_tutorial(self) -> bool:
        return not self.seen_tutorial and self.receives_rephrasings

    @property
    def post_chat_url(self) -> str:
        return (
            POST_CHAT_URL.format(
                respondent_id=self.response_id,
                treatment=self.treatment_code or "",
                position=self.position.value,
            )
            if POST_CHAT_URL
            else None
        )

    @property
    def no_chat_url(self) -> str:
        return (
            NO_CHAT_URL.format(
                respondent_id=self.response_id, position=self.position.value
            )
            if NO_CHAT_URL
            else None
        )

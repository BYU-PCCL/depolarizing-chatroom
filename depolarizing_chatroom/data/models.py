import enum

from sqlalchemy import (
    Integer,
    Column,
    Text,
    String,
    ForeignKey,
    Boolean,
    DateTime,
)
from sqlalchemy.orm import relationship

from .database import Base
from ..constants import POST_SURVEY_URL


class Chatroom(Base):
    __tablename__ = "chatrooms"

    id = Column(Integer, primary_key=True)
    prompt = Column(String(320))

    # relationship (one-to-many with users, one-to-many with messages)
    users = relationship("User", back_populates="chatroom")
    messages = relationship("Message", back_populates="chatroom")
    limit_reached = Column(Boolean, default=False)

    def __repr__(self):
        return f"{self.prompt}, {self.users}"


class Rephrasing(Base):
    __tablename__ = "rephrasings"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id"))
    body = Column(Text, nullable=False)
    edited_body = Column(Text)

    # relationship (many-to-one with messages)
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

    # relationship (one-to-many with rephrasings, many-to-one with chatroom, many-to-one
    # with user)
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

    def __repr__(self) -> str:
        return f"{self.user}@{self.chatroom}: {self.body}"


class UserPosition(enum.Enum):
    OPPOSE = "oppose"
    SUPPORT = "support"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    chatroom_id = Column(Integer, ForeignKey("chatrooms.id"))
    response_id = Column(String(320), nullable=False)
    started_waiting = Column(DateTime)
    finished_waiting = Column(DateTime)
    waiting_session_id = Column(String)
    # Treatment key:
    # 1: Supports stricter gun laws, treated with GPT-3. Matched with 5.
    # 2: Supports stricter gun laws, talks to person treated with GPT-3. Matched with 4.
    # 3: Supports stricter gun laws, untreated conversation. Matched with 6.
    # 4: Opposes stricter gun laws, treated with GPT-3. Matched with 2.
    # 5: Opposes stricter gun laws, talks to person treated with GPT-3. Matched with 1.
    # 6: Opposes stricter gun laws, untreated conversation. Matched with 3.
    treatment = Column(Integer)
    view = Column(String(), nullable=True)
    leave_reason = Column(Text)

    # relationship (many-to-one with chatrooms, one-to-many with messages, one-to-many
    # with responses)
    chatroom = relationship("Chatroom", back_populates="users")
    messages = relationship(
        "Message", back_populates="user", order_by=Message.send_time.desc
    )

    @property
    def position(self) -> UserPosition:
        if self.treatment <= 3:
            return UserPosition.SUPPORT
        return UserPosition.OPPOSE

    @property
    def receives_rephrasings(self) -> bool:
        if self.treatment < 1:
            return False
        return (self.treatment - 1) % 3 == 0

    @property
    def in_untreated_conversation(self) -> bool:
        return self.treatment % 3 == 0

    @property
    def match_with(self) -> int:
        if self.treatment == 1:
            return 5
        if self.treatment == 2:
            return 4
        if self.treatment == 3:
            return 6
        if self.treatment == 4:
            return 2
        if self.treatment == 5:
            return 1
        if self.treatment == 6:
            return 3
        return None

    @property
    def post_survey_url(self) -> str:
        return (
            POST_SURVEY_URL.format(link_id=self.response_id, treatment=self.treatment)
            if POST_SURVEY_URL
            else None
        )

    def __repr__(self):
        return f"<User response_id={self.response_id}>"
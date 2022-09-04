import enum

from sqlalchemy import (
    Integer,
    Float,
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
    code_id = Column(Integer, ForeignKey("codes.id"))
    prompt = Column(String(320))

    # relationship (one-to-many with users, one-to-many with messages, many-to-one
    # with codes)
    users = relationship("User", back_populates="chatroom")
    messages = relationship("Message", back_populates="chatroom")
    code = relationship("Code", back_populates="chatrooms")

    def __repr__(self):
        return f"{self.code}:{self.prompt}, {self.users}"


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
        return (
            f"{self.user}@{self.chatroom}: {self.body}"
            # f"{self.user}@{self.chatroom}: {self.message}\n"
            # f"{self.rephrasing}\n"
            # f"{self.trans_accepted}"
        )


class UserPosition(enum.Enum):
    OPPOSE = "oppose"
    SUPPORT = "support"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    chatroom_id = Column(Integer, ForeignKey("chatrooms.id"))
    code_id = Column(Integer, ForeignKey("codes.id"))
    response_id = Column(String(320), nullable=False)
    started_waiting = Column(DateTime)
    finished_waiting = Column(DateTime)
    waiting_session_id = Column(String)
    message_count = Column(Integer, default=0)
    status = Column(String(20), default="code")
    # Treatment key:
    # 1: Supports stricter gun laws, treated with GPT-3. Matched with 5.
    # 2: Supports stricter gun laws, talks to person treated with GPT-3. Matched with 4.
    # 3: Supports stricter gun laws, untreated conversation. Matched with 6.
    # 4: Opposes stricter gun laws, treated with GPT-3. Matched with 2.
    # 5: Opposes stricter gun laws, talks to person treated with GPT-3. Matched with 1.
    # 6: Opposes stricter gun laws, untreated conversation. Matched with 3.
    # 7: Talking to GPT-3, always treated with GPT-3.
    treatment = Column(Integer)
    view = Column(String(), nullable=True)
    # TODO: Keep track of how long the respondent has been waiting for a response.

    # relationship (many-to-one with chatrooms, one-to-many with messages,
    # many-to-one with codes, one-to-many with responses)
    chatroom = relationship("Chatroom", back_populates="users")
    messages = relationship(
        "Message", back_populates="user", order_by=Message.send_time.desc
    )
    code = relationship("Code", back_populates="users")
    responses = relationship("Response", back_populates="user")

    @property
    def position(self) -> UserPosition:
        if self.treatment < 3:
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
        return POST_SURVEY_URL.format(
            link_id=self.response_id, treatment=self.treatment
        )

    def __repr__(self):
        return f"<User response_id={self.response_id}>"


class Response(Base):
    __tablename__ = "responses"

    id = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey("users.id"))
    code_id = Column(Integer, ForeignKey("codes.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    _response = Column(Text)  # potential list delineated by pipes |
    is_post = Column(Boolean, nullable=False, default=False)

    # relationship (many-to-one with Codes, many-to-one with Users, many-to-one with
    # Questions)
    code = relationship("Code", back_populates="responses")
    user = relationship("User", back_populates="responses")
    question = relationship("Question", back_populates="responses")

    @property
    def response(self):
        return [x for x in self._response.split("|")]

    @response.setter
    def response(self, vals):
        self._response = "|".join(vals)

    def __repr__(self):
        return f"{self.user}@{self.question}: {self.response}"


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    code_id = Column(Integer, ForeignKey("codes.id"))
    question = Column(Text, nullable=False)
    type = Column(String(20), nullable=False)
    number = Column(Integer, nullable=False)  # question number
    start = Column(Float)
    step = Column(Float)
    is_post = Column(Boolean, default=False)
    _options = Column(Text)  # pipe | delineated options
    _range = Column(Text)  # pipe | delineated min and max (for grid)
    _questions = Column(Text)  # pipe | delineated questions (for grid, each row)

    # relationship (many-to-one with Codes, one-to-many with Responses)
    responses = relationship("Response", back_populates="question")
    code = relationship("Code", back_populates="questions")

    @property
    def options(self):
        return [x for x in self._options.split("|")]

    @options.setter
    def options(self, vals):
        self._options = "|".join(vals)

    @property
    def range(self):
        return [float(x) for x in self._range.split("|")]

    @range.setter
    def range(self, vals):
        self._range = "|".join(list(map(str, vals)))

    @property
    def questions(self):
        return [x for x in self._questions.split("|")]

    @questions.setter
    def questions(self, vals):
        self._questions = "|".join(vals)

    def __repr__(self):
        return self.question


class Code(Base):
    __tablename__ = "codes"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), nullable=False, unique=True)
    expiry = Column(DateTime, nullable=False)

    # relationship (one-to-many with chatrooms, one-to-many with user, one-to-many
    # with responses, one-to-many with questions)
    chatrooms = relationship("Chatroom", back_populates="code")
    users = relationship("User", back_populates="code")
    responses = relationship("Response", back_populates="code")
    questions = relationship(
        "Question", back_populates="code", order_by=Question.number.desc
    )

    def __repr__(self):
        return self.code

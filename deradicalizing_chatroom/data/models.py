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

    # relationship (many-to-one with messages)
    message = relationship(
        "Message", back_populates="rephrasings", foreign_keys=message_id
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    chatroom_id = Column(Integer, ForeignKey("chatrooms.id"))
    sender_id = Column(Integer, ForeignKey("users.id"))
    body = Column(Text, nullable=False)
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
    )
    accepted_rephrasing = relationship(
        "Rephrasing", foreign_keys=accepted_rephrasing_id
    )
    chatroom = relationship("Chatroom", back_populates="messages")
    user = relationship("User", back_populates="messages")

    def __repr__(self) -> str:
        return (
            f"{self.user}@{self.chatroom}: {self.message}"
            # f"{self.user}@{self.chatroom}: {self.message}\n"
            # f"{self.rephrasing}\n"
            # f"{self.trans_accepted}"
        )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    chatroom_id = Column(Integer, ForeignKey("chatrooms.id"))
    code_id = Column(Integer, ForeignKey("codes.id"))
    email = Column(String(320), nullable=False, unique=True)
    affiliation = Column(String(320), nullable=False)
    password = Column(String(64), nullable=False)
    salt = Column(String(7), nullable=False)
    # TODO: WHAT DOES THIS DO?
    curq = Column(Integer, default=1)
    username = Column(String(320))
    color = Column(String(7))
    waiting = Column(DateTime)
    message_count = Column(Integer, default=0)
    status = Column(String(20), default="code")
    # waiting = db.Column(db.DateTime)

    # relationship (many-to-one with chatrooms, one-to-many with messages,
    # many-to-one with codes, one-to-many with responses)
    chatroom = relationship("Chatroom", back_populates="users")
    messages = relationship(
        "Message", back_populates="user", order_by=Message.send_time.desc
    )
    code = relationship("Code", back_populates="users")
    responses = relationship("Response", back_populates="user")

    def __repr__(self):
        return f"{self.username}:{self.code}"


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

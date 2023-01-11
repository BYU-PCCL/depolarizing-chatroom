import asyncio
import os
import random
import time
from datetime import datetime
from typing import Optional

from fastapi import Depends
from pydantic import BaseModel

from ..constants import (
    MIN_COUNTED_MESSAGE_WORD_COUNT,
    MIN_REPHRASING_TURNS,
    REPHRASE_EVERY_N_TURNS,
    REQUIRED_REPHRASINGS,
    SOCKET_NAMESPACE_CHATROOM,
)
from ..data import models
from ..data.crud import access
from ..logger import format_parameterized_log_message, logger
from ..rephrasings import generate_rephrasings
from ..server import (
    app,
    executor,
    get_templates,
    get_user_from_auth_code,
    socket_manager,
)
from ..socketio import SessionSocketAsyncNamespace, SocketSession
from ..util import calculate_turns, last_n_turns


# Really hacky, shouldn't be here, helps us avoid racking up OpenAI API calls
# during load testing
FAKE_REPHRASINGS = os.environ.get("FAKE_REPHRASINGS", "0").lower() == "1"


class InitialViewBody(BaseModel):
    view: str


@app.get("/chatroom")
async def get_chatroom(user: models.User = Depends(get_user_from_auth_code)):
    if not (chatroom := user.chatroom):
        # If user is not in a chatroom, redirect to waiting room
        logger.warning(
            format_parameterized_log_message(
                "User attempted to join chatroom but is not in one, redirecting to "
                "waiting room",
                user_id=user.id,
            )
        )
        return {"redirect": "waiting"}
    chatroom_id = chatroom.id
    async with access.commit_after():
        # Get all previously sent messages in the chatroom
        messages = await access.chatroom_messages(chatroom)
        # Swap first two messages if chatroom.swap_view_messages is true
        # Get other user in chatroom
        partner = await access.other_user_in_chatroom(chatroom_id, user.id)
    partner_online = partner.finished_chat_time is None
    logger.debug(
        format_parameterized_log_message(
            "GET /chatroom",
            user_id=user.id,
            chatroom_id=chatroom_id,
            message_count=len(messages),
            partner_online=partner_online,
        )
    )
    return {
        "messages": messages,
        "limitReached": chatroom.limit_reached,
        "partnerOnline": partner.chatroom_session_id is not None,
        "id": chatroom_id,
    }


@app.post("/initial-view")
async def initial_view(
    body: InitialViewBody,
    user: models.User = Depends(get_user_from_auth_code),
):
    if not user.chatroom or user.view:
        logger.warning(
            format_parameterized_log_message(
                "User attempted to set initial view but is not in a chatroom or has "
                "already set their view",
                user_id=user.id,
                chatroom_id=user.chatroom_id,
                has_view=user.view is not None,
            )
        )
        # This will effectively prevent the user from ever changing their view
        return
    # At this point, the user will already have a chatroom
    chatroom = user.chatroom
    async with access.commit_after():
        user.view = body.view
        access.add_message(chatroom.id, user.id, body.view)
        access.save_event(user.id, "set_view")
    logger.info(
        format_parameterized_log_message(
            "User set initial view",
            user_id=user.id,
            chatroom_id=chatroom.id,
            view_length=len(body.view),
        )
    )


class ChatroomSocketSession(SocketSession):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._chatroom = self._user.chatroom

    async def on_connect(self) -> Optional[bool]:
        if not self._chatroom:
            return False

        logger.debug(
            format_parameterized_log_message(
                "User connected to chatroom",
                user_id=self._user.id,
                chatroom_id=self._chatroom.id,
                session_id=self._session_id,
            )
        )

        async with access.commit_after():
            self._user.chatroom_session_id = self._session_id

            if self._user.started_chat_time is None:
                self._user.started_chat_time = datetime.now()

            self._user.finished_chat_time = None

            access.save_event(self._user.id, "join_chatroom", data=self._session_id)

        self._sio.enter_room(self._session_id, self._user.chatroom_id)

        await self._sio.emit(
            "partner_status",
            True,
            to=self._user.chatroom_id,
            skip_sid=self._session_id,
        )

        messages = []
        for message in await access.chatroom_messages(self._chatroom):
            messages.append(
                {
                    "id": message.id,
                    "user_id": message.sender_id,
                    "message": message.selected_body,
                }
            )

        await self._sio.emit("messages", messages, to=self._session_id)

    async def on_disconnect(self) -> None:
        if not self._chatroom:
            return

        await self._sio.emit(
            "partner_status", False, to=self._chatroom.id, skip_sid=self._session_id
        )

        async with access.commit_after():
            self._user.chatroom_session_id = None
            access.save_event(self._user.id, "leave_chatroom", data=self._session_id)
            self._user.finished_chat_time = datetime.now()

        logger.debug(
            format_parameterized_log_message(
                "User disconnected from chatroom",
                user_id=self._user.id,
                chatroom_id=self._chatroom.id,
                session_id=self._session_id,
            )
        )

    async def on_rephrasing_response(self, body) -> None:
        message_id = body["message_id"]
        message_body = body["body"]
        message = await access.message(message_id)

        if (
            message.sender_id != self._user.id
            or message.chatroom_id != self._chatroom.id
        ):
            logger.warning(
                format_parameterized_log_message(
                    "User sent receiving rephrasing response for message they didn't "
                    "send",
                    user_id=self._user.id,
                    chatroom_id=self._chatroom.id,
                )
            )
            return

        async with access.commit_after():
            strategy = None
            if rephrasing_id := body.get("rephrasing_id"):
                rephrasing = await access.rephrasing(rephrasing_id)
                strategy = rephrasing.strategy

                if rephrasing.message_id != message.id:
                    return

                if rephrasing.body != message_body:
                    rephrasing.edited_body = message_body

                message.accepted_rephrasing_id = rephrasing.id
            elif message.body != message_body:
                message.edited_body = message_body
            access.save_event(
                self._user.id,
                "rephrasing_response",
                data={
                    "rephrasing_id": rephrasing_id,
                    "strategy": strategy,
                    "edited_message": message.body != message_body,
                },
            )

        await self._send_message_to_chatroom(message.selected_body)

        logger.debug(
            format_parameterized_log_message(
                "User sent rephrasing response",
                user_id=self._user.id,
                chatroom_id=self._chatroom.id,
                message_id=message.id,
                rephrasing_id=rephrasing_id,
                message_length=len(message_body),
            )
        )

    async def on_typing(self) -> None:
        # TODO: Determine whether this is going to lock up the database
        await self._sio.emit(
            "typing",
            to=self._chatroom.id,
            skip_sid=self._session_id,
        )
        async with access.commit_after():
            access.save_event(self._user.id, "typing")

    async def on_online(self) -> None:
        await self._sio.emit(
            "partner_status",
            True,
            to=self._chatroom.id,
            skip_sid=self._session_id,
        )

    async def on_event(self, body) -> None:
        if not (event_type := body.get("type")):
            logger.warning(
                format_parameterized_log_message(
                    "User sent event with no type",
                    user_id=self._user.id,
                    chatroom_id=self._chatroom.id,
                )
            )
            return
        time = body.get("time")
        if time:
            if not isinstance(time, int):
                logger.warning(
                    format_parameterized_log_message(
                        "User sent event with invalid timestamp",
                        user_id=self._user.id,
                        chatroom_id=self._chatroom.id,
                    )
                )
                return
            time = datetime.fromtimestamp(time / 1000)
        data = body.get("data")
        async with access.commit_after():
            access.save_event(self._user.id, event_type, data=data, time=time)
        logger.debug(
            format_parameterized_log_message(
                "User sent chatroom event",
                user_id=self._user.id,
                chatroom_id=self._chatroom.id,
                event_type=event_type,
            )
        )

    async def on_message(self, body) -> None:
        # TODO: Break this method up

        message_body = body["body"]

        logger.debug(
            format_parameterized_log_message(
                "User sent message to chatroom",
                user_id=self._user.id,
                chatroom_id=self._chatroom.id,
                message_length=len(message_body),
            )
        )

        chatroom_messages = await access.chatroom_messages(
            self._chatroom, select_users=True, select_rephrasings=True
        )

        # Count messages, not including anything with fewer than 4 words (just counting
        # by spaces), a turn only happens if one user sends at least one message with at
        # least 4 words, and we need 3 turns, or three alternating chunks of at least
        # one message with at least 4 words. So we calculate turns and only send
        # rephrasings if we have turns % 3 == 0. Probably a little expensive, but it
        # seems fine. We'll rephrase the first message sent because the first two
        # messages are input before the chat starts.

        will_attempt_rephrasings = False
        user_position = self._user.position.value
        (
            turn_count,
            user_turn_count,
            partner_turn_count,
            last_turn_counted,
            turns,
        ) = calculate_turns(
            [
                {
                    "position": message.user.position.value,
                    "body": message.selected_body,
                    # TODO: Figure out if this is an expensive operation (or maybe it's
                    #  cached for us?)
                    "rephrased": len(message.rephrasings) > 0,
                }
                for message in chatroom_messages
            ],
            user_position,
        )
        if self._user.receives_rephrasings:
            message_is_min_length = (
                len(message_body.split()) >= MIN_COUNTED_MESSAGE_WORD_COUNT
            )

            # Is this the first message in a new turn? That is, was the last message
            # sent by the other user?
            new_turn = (
                chatroom_messages and self._user.id != chatroom_messages[-1].sender_id
            )

            # TODO: Explain this logic (it's pretty straightforward)
            if message_is_min_length and (new_turn or not last_turn_counted):
                user_turn_count += 1
                will_attempt_rephrasings = (
                    turn_count >= MIN_REPHRASING_TURNS
                    and user_turn_count % REPHRASE_EVERY_N_TURNS == 0
                )

        async with access.commit_after():
            # We end the conversation the turn AFTER the last turn we rephrase,
            # to give the untreated user a chance to respond to the rephrasing.
            # That's why we use partner_turn_count and _not_
            # user.receives_rephrasings—we want it to be the untreated user who ends
            # up ending the conversation
            if (
                partner_turn_count / REPHRASE_EVERY_N_TURNS
            ) >= REQUIRED_REPHRASINGS and (
                not self._user.receives_rephrasings
                or self._user.in_control_conversation
            ):
                logger.debug(
                    format_parameterized_log_message(
                        "User reached required rephrasing count, updating chatroom "
                        "status",
                        user_id=self._user.id,
                        chatroom_id=self._chatroom.id,
                        user_turn_count=user_turn_count,
                        receives_rephrasings=self._user.receives_rephrasings,
                        in_control_conversation=self._user.in_control_conversation,
                    )
                )
                self._chatroom.limit_reached = True

            message = access.add_message(self._chatroom.id, self._user.id, message_body)

            access.save_event(
                self._user.id,
                "sent_message",
                data={
                    "message_id": message.id,
                    "will_attempt_rephrasings": will_attempt_rephrasings,
                },
            )

        await self._sio.emit(
            "rephrasings_status",
            dict(will_attempt=will_attempt_rephrasings),
            to=self._session_id,
        )

        # Give socket manager a chance to send the rephrasings status message
        # TODO: Unclear that we need this—I think that things were blocking because
        #  rephrasings were done in a blocking way
        await asyncio.sleep(0.2)

        # TODO: This is a horrible way to organize a function, makes it hard to
        #  understand
        if will_attempt_rephrasings:
            await self._send_rephrasings(message, turns, user_turn_count)
        else:
            await self._send_message_to_chatroom(message_body)

    async def _send_rephrasings(self, message, turns, user_turn_count) -> None:
        user_position = self._user.position.value
        # TODO: Figure out why we need a function to get this and do dependency
        #  injection the right way instead
        templates = get_templates()

        last_turn_is_user = (
            user_turn_count > 0 and turns[-1][0]["position"] == user_position
        )

        # 10 doesn't mean anything, it's just a number high enough that I imagine we'd
        # never construct a template that uses that many turns.
        template_turns = last_n_turns(turns, 10)

        template_rephrasing_message = {
            "position": user_position,
            "body": message.selected_body,
        }

        if last_turn_is_user:
            # Add user's message to existing turn
            template_turns[-1].append(template_rephrasing_message)
        else:
            # Create new turn for user's message
            template_turns.append([template_rephrasing_message])

        async with access.commit_after():
            # Time how long it takes to generate rephrasings
            # (I'm sure this isn't accurate because we're in asyncland but it's helpful
            # to get an idea)
            start_time = time.perf_counter()
            if not FAKE_REPHRASINGS:
                rephrasings = [
                    access.add_rephrasing(message.id, response, strategy)
                    for strategy, response in (
                        await generate_rephrasings(executor, templates, template_turns)
                    ).items()
                ]
            else:
                logger.debug(
                    "FAKE_REPHRASINGS is set to true, sending fake rephrasings"
                )
                # TODO: Fix this awful hacky code, figure out how to inject this or
                #  monkey patch it
                # Wait a short amount of time to simulate network operation
                await asyncio.sleep(random.random() * 2)
                rephrasings = [
                    access.add_rephrasing(message.id, "rephrasing 1", "strategy 1"),
                    access.add_rephrasing(message.id, "rephrasing 2", "strategy 2"),
                    access.add_rephrasing(message.id, "rephrasing 3", "strategy 3"),
                ]
            end_time = time.perf_counter()
            logger.debug(
                format_parameterized_log_message(
                    "Generated rephrasings",
                    user_id=self._user.id,
                    chatroom_id=self._chatroom.id,
                    rephrasing_count=len(rephrasings),
                    total_seconds=f"{end_time - start_time:.2f}",
                )
            )

            access.save_event(
                self._user.id, "rephrasings_response", data={"message_id": message.id}
            )

        # We want to present rephrasings in a random order
        random.shuffle(rephrasings)

        await self._sio.emit(
            "rephrasings_response",
            dict(
                message_id=message.id,
                body=message.body,
                rephrasings=[{"id": r.id, "body": r.body} for r in rephrasings],
            ),
            to=self._session_id,
        )
        logger.debug(
            format_parameterized_log_message(
                "Sent rephrasings to user",
                user_id=self._user.id,
                chatroom_id=self._chatroom.id,
                message_id=message.id,
                rephrasings=[r.id for r in rephrasings],
            )
        )

    async def _redirect_to_waiting(self, session_id) -> None:
        await self._sio.emit("redirect", dict(to="waiting"), to=session_id)

    async def _send_message_to_chatroom(self, message_body) -> None:
        await self._sio.emit(
            f"new_message",
            dict(user_id=self._user.id, message=message_body),
            to=self._chatroom.id,
        )
        logger.debug(
            format_parameterized_log_message(
                "Broadcasted message to chatroom",
                user_id=self._user.id,
                chatroom_id=self._chatroom.id,
                message_length=len(message_body),
            )
        )
        if self._chatroom.limit_reached:
            await self._sio.emit("min_limit_reached", to=self._chatroom.id)


# noinspection PyProtectedMember
socket_manager._sio.register_namespace(
    SessionSocketAsyncNamespace(ChatroomSocketSession, SOCKET_NAMESPACE_CHATROOM)
)

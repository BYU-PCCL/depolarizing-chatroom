import random
from datetime import datetime
from typing import Optional

from fastapi import Depends
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import IntegrityError

from ..constants import SOCKET_NAMESPACE_WAITING_ROOM
from ..data import models
from ..data.crud import access
from ..data.models import UserTreatment
from ..logger import format_parameterized_log_message, logger
from ..server import app, get_user_from_auth_code, socket_manager
from ..socketio import SessionSocketAsyncNamespace, SocketSession


@app.get("/waiting-status")
async def get_waiting_status(user: models.User = Depends(get_user_from_auth_code)):
    # Check if user is in chatroom
    chatroom = user.chatroom
    if chatroom:
        other_user = await access.other_user_in_chatroom(chatroom.id, user.id)
        if other_user.waiting_session_id is None:
            partner_status = "offline"
        else:
            partner_status = "matched"
    else:
        partner_status = "waiting"

    logger.debug(
        format_parameterized_log_message(
            "GET /waiting-room",
            user_id=user.id,
            partner_status=partner_status,
        )
    )
    return {"partnerStatus": partner_status}


class WaitingRoomSocketSession(SocketSession):
    async def on_connect(self) -> None:
        user = self._user

        async with access.commit_after():
            user.waiting_session_id = self._session_id
            access.save_event(user.id, "join_waiting_room", self._session_id)

        logger.debug(
            format_parameterized_log_message(
                "User connected to waiting room",
                user_id=user.id,
                waiting_session_id=self._session_id,
                page=self._auth.get("page"),
            )
        )

        # Note that having a chatroom only means that the user has been matched, not
        # that the chatroom is ready. Both users must submit views before the chatroom
        # is ready.
        partner = await self._partner()
        if partner:
            # Make sure partner gets update if we disconnect and reconnect while they're
            # in the waiting room
            await self._update_partner_status("matched")
            logger.debug(
                format_parameterized_log_message(
                    "User joined waiting room after matching, notified partner",
                    user_id=user.id,
                    partner_user_id=partner.id,
                )
            )
        if (redirect_target := await self._redirect_target()) is not None:
            await self._redirect(redirect_target)
            async with access.commit_after():
                access.save_event(user.id, "waiting_room_redirect", redirect_target)
            logger.debug(
                format_parameterized_log_message(
                    "Redirected user after joining waiting room",
                    user_id=user.id,
                    redirect=redirect_target,
                )
            )
            # If we're being redirected to the chatroom—which means both users have
            # filled out their views—then we should redirect our partner if they're
            # online too.
            if redirect_target == "chatroom" and partner:
                await self._redirect(redirect_target, partner.waiting_session_id)
                async with access.commit_after():
                    access.save_event(user.id, "waiting_room_redirect_partner")
                logger.debug(
                    format_parameterized_log_message(
                        "Redirected partner to chatroom after joining waiting room",
                        user_id=user.id,
                        partner_user_id=partner.id,
                    )
                )
            return

        # Add user to waiting room
        if not user.started_waiting_time:
            async with access.commit_after():
                user.started_waiting_time = datetime.now()

        # End running transaction
        await db.session.commit()

        # Get all available matches by position
        matching_users = await access.users_in_waiting_room(
            position=user.match_with, matched=False
        )

        matching_user_id = None
        match_attempt = 0

        user_id = user.id

        if matching_users:
            matching_user_ids = [u.id for u in matching_users]
            logger.debug(
                format_parameterized_log_message(
                    "Found users to match with",
                    user_id=user.id,
                    user_position=user.position.name.lower(),
                    matching_users=matching_user_ids,
                )
            )

            # Try to safely match with every matching user in the waiting room
            # TODO: Consider moving this messy business logic somewhere else
            for match_attempt, matching_user_id in enumerate(
                matching_user_ids, start=1
            ):
                try:
                    async with access.session.begin_nested():
                        # This should fail if the other user has already matched with
                        # someone else, because it commits to the database
                        access.add(models.MatchedUser(id=matching_user_id))
                        access.add(models.MatchedUser(id=user_id))
                # Handle case where user has already been matched (in trying to avoid
                # a race condition)
                except IntegrityError:
                    # Rollback session to maintain integrity—if we don't do this then we
                    # won't be able to access attributes on ORM objects, like user.id
                    await access.session.rollback()
                    logger.warning(
                        format_parameterized_log_message(
                            "Attempted to match user with another user who has already "
                            "been matched, skipping",
                            user_id=user_id,
                            matching_user_id=matching_user_id,
                        )
                    )
                    # We can't match with this user, so set it to None
                    matching_user_id = None
                    # Couldn't insert matched user to matched user table uniquely, so
                    # continue to next user
                    continue
                # If we get here, we've found a match. Use matching_user defined by this
                # loop
                break

        if matching_user_id is None:
            # No match found, wait for another user to join
            logger.debug(
                format_parameterized_log_message(
                    "No matches found for user, waiting for another user to join",
                    user_id=user_id,
                    match_attempts=match_attempt,
                )
            )
            return

        # Reload user and matching user because rollback might have screwed us over
        self._user = user = await access.user(user_id)
        matching_user = await access.user(matching_user_id)

        # And there's no reason this should ever happen
        assert matching_user.id != user.id

        async with access.commit_after():
            # Set found match time to now
            found_match_time = datetime.now()
            matching_user.found_match_time = found_match_time
            user.found_match_time = found_match_time

            # Create a chatroom and put users together
            chatroom = access.create_chatroom()
            user.chatroom = chatroom
            matching_user.chatroom = chatroom

            logger.info(
                format_parameterized_log_message(
                    "Found match for user, created chatroom",
                    user_id=user.id,
                    partner_user_id=matching_user.id,
                    chatroom_id=chatroom.id,
                )
            )

            # Randomly select treatment for user...
            treatment = random.choice(list(UserTreatment.__members__.values()))
            user.treatment = treatment
            # ...and for the matching user
            matching_user.treatment = treatment.match_with

            logger.debug(
                format_parameterized_log_message(
                    "Set treatment for user and matching user",
                    user_id=user.id,
                    partner_user_id=matching_user.id,
                    user_position=user.position.name.lower(),
                    user_treatment=user.treatment.name.lower(),
                    partner_position=matching_user.position.name.lower(),
                    partner_treatment=matching_user.treatment.name.lower(),
                    chatroom_id=chatroom.id,
                )
            )
            access.save_event(user.id, "create_chatroom", chatroom.id)

        async with access.commit_after():
            # Send messages to both users
            for session_user, matched_with in zip(
                (user, matching_user), (matching_user, user)
            ):
                if session_user.needs_tutorial:
                    redirect_to = "tutorial"
                    session_user.seen_tutorial = True
                else:
                    redirect_to = "view"
                logger.debug(
                    format_parameterized_log_message(
                        "Redirecting user after matching",
                        user_id=session_user.id,
                        matched_with=matched_with.id,
                        user_treatment=session_user.treatment.name.lower(),
                        redirect=redirect_to,
                    )
                )
                await self._redirect(redirect_to, session_user.waiting_session_id)
                # This is used for testing only, but we need to know who a user was
                # paired with
                # TODO: Make this overall less hacky
                await self._sio.emit(
                    "matched_with",
                    [session_user.id, matched_with.id],
                    to=session_user.waiting_session_id,
                )

    async def on_disconnect(self) -> None:
        # Remove user from waiting room pool
        user = self._user
        async with access.commit_after():
            user.finished_waiting_time = datetime.now()
            user.waiting_session_id = None
            access.save_event(user.id, "leave_waiting_room", self._session_id)
        logger.debug(
            format_parameterized_log_message(
                "User disconnected from waiting room",
                user_id=user.id,
                waiting_session_id=self._session_id,
            )
        )
        # Notify other user if this user had matched
        if (chatroom := user.chatroom) and (
            other_user := await access.other_user_in_chatroom(chatroom.id, user.id)
        ):
            if not other_user.waiting_session_id:
                return
            await self._update_partner_status("offline")
            logger.debug(
                format_parameterized_log_message(
                    "Notified partner that this user has disconnected",
                    user_id=user.id,
                    partner_user_id=other_user.id,
                    user_session_id=self._session_id,
                    other_user_session_id=other_user.waiting_session_id,
                )
            )

    async def _redirect_target(self) -> Optional[str]:
        # TODO: This horrible redirect mess is what I get for not thinking about this
        #  more—seems like a bad approach

        page = self._auth.get("page")

        # Don't ever redirect if the user is in the tutorial
        if page == "tutorial":
            return None

        # If user is UNMATCHED, the user is right to be in the waiting room, so don't
        # redirect
        if not self._user.chatroom:
            return None

        # If user HAS matched, but HASN'T submitted a view, redirect to view
        if not self._user.view:
            return "view"

        partner = await self._partner()
        # If user HAS matched, HAS submitted a view, check if other user has submitted—
        # if they have, then we're done waiting, so redirect to chatroom
        if partner.view:
            return "chatroom"

        # If user is in the view page but has ALREADY submitted a view, redirect to
        # waiting page
        if page == "view":
            return "waiting"

        # Redirect to tutorial if they haven't seen it—this won't happen twice
        if self._user.needs_tutorial:
            async with access.commit_after():
                self._user.seen_tutorial = True
            logger.debug(
                format_parameterized_log_message(
                    "User is redirecting to tutorial, setting seen_tutorial to True"
                )
            )
            return "tutorial"

        # This return statement is here only to be explicit. This will happen only if
        # each of the following are true:
        # - The user has a chatroom (they've been matched)
        # - The user has submitted a view
        # - The user has either seen the tutorial or doesn't need to
        # - The other user has not yet finished their pre-chat steps
        return None

    async def _redirect(self, to: str, session_id=None) -> None:
        await self._sio.emit(
            "redirect",
            dict(to=to),
            to=session_id if session_id is not None else self._session_id,
        )
        logger.debug(
            format_parameterized_log_message(
                "Sent redirect message to user",
                # Note here that the user redirected might not be the user who sent the
                # message because we allow passing in a session_id
                sending_user_id=self._user.id,
                redirect=to,
                session_id=session_id,
            )
        )

    async def _partner(self) -> Optional[models.User]:
        if (chatroom := self._user.chatroom) and (
            other_user := await access.other_user_in_chatroom(
                chatroom.id, self._user.id
            )
        ):
            # If user is in chatroom but not in waiting room, don't return them—they're
            # not online
            if not other_user.waiting_session_id:
                return

            return other_user

    async def _update_partner_status(self, status) -> None:
        if not (partner := await self._partner()):
            return

        await self._sio.emit("partner_status", status, partner.waiting_session_id)


# noinspection PyProtectedMember
socket_manager._sio.register_namespace(
    SessionSocketAsyncNamespace(WaitingRoomSocketSession, SOCKET_NAMESPACE_WAITING_ROOM)
)

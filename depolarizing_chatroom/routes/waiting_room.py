import random
import uuid
from datetime import datetime
from typing import Optional

from fastapi import Depends
from sqlalchemy import case, insert, tuple_, update
from sqlalchemy.orm.exc import StaleDataError

from ..constants import SOCKET_NAMESPACE_WAITING_ROOM
from ..data import models
from ..data.crud import access
from ..data.models import UserTreatment
from ..logger import format_parameterized_log_message, logger
from ..server import app, get_user_from_auth_code, socket_manager
from ..socketio_util import SessionSocketAsyncNamespace, SocketSession


@app.get("/waiting-status")
async def get_waiting_status(user: models.User = Depends(get_user_from_auth_code)):
    # Check if user is in chatroom
    chatroom = user.chatroom
    if chatroom:
        other_user = await access.other_user_in_chatroom(chatroom.id, user.id)
        if not other_user or other_user.waiting_session_id is None:
            partner_status = "offline"
            if not other_user:
                logger.error(
                    format_parameterized_log_message(
                        "User is in chatroom without partner",
                        user_id=user.id,
                        chatroom_id=chatroom.id,
                    )
                )
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
            access.save_event(user.id, "join_waiting_room", data=self._session_id)

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
        if partner and partner.waiting_session_id:
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
        try:
            if (redirect_target := await self._redirect_target()) is not None:
                await self._redirect(redirect_target)
                async with access.commit_after():
                    access.save_event(
                        user.id, "waiting_room_redirect", data=redirect_target
                    )
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
        except RuntimeError:
            logger.exception(
                format_parameterized_log_message(
                    "Error redirecting user after joining waiting room",
                    user_id=user.id,
                )
            )
            return

        # TODO: Move the rest of this function into something else
        # Not elegant, but we don't want to try rematching if the user is already in a
        # chatroom.
        if user.chatroom_id is not None:
            logger.debug(
                format_parameterized_log_message(
                    "User is already in a chatroom, exiting waiting room",
                    user_id=user.id,
                    chatroom_id=user.chatroom_id,
                )
            )
            return

        # Add user to waiting room
        if not user.started_waiting_time:
            async with access.commit_after():
                user.started_waiting_time = datetime.now()

        # Save user ID for error message if needed
        user_id = user.id

        # End running transaction to explicitly start a new one
        await access.session.commit()

        try:
            async with access.session.begin():
                # Update user at beginning of this transaction
                user = await access.user(user_id)
                # Get first available match by position
                match_user = await access.random_user_to_match_with(user)

                if match_user is None:
                    # No match found, wait for another user to join
                    logger.debug(
                        format_parameterized_log_message(
                            "No match found for user, waiting for another user to join",
                            user_id=user.id,
                        )
                    )
                    return

                # We want to be able to log the matched user's ID but SQLAlchemy will
                # lock up the database if we try to access it after something goes awry
                match_user_id = match_user.id

                # Set found match time to now
                found_match_time = datetime.now()

                # Randomly select treatment for user...
                treatment = random.choice(list(UserTreatment.__members__.values()))
                # ...and their partner
                partner_treatment = treatment.match_with

                # This is a CTE, or Common Table Expression, which is a temporary table
                # that can be used in a query. We use it to create a chatroom and
                # associate it with both users in a single query.
                create_chatroom_cte = (
                    insert(models.Chatroom)
                    .values(swap_view_messages=random.choice([True, False]))
                    .returning(models.Chatroom.id)
                    .cte("create_chatroom")
                )

                # Save these just in case SQLAlchemy does some dynamic attribute lookup
                # that changes these values before we'd expect
                user_match_version = user.match_version
                match_user_match_version = match_user.match_version

                # This horrible query manages to avoid deadlocks by creating the
                # chatroom and updating both users in a single query.
                update_users_statement = (
                    update(models.User)
                    .where(
                        # The only reason we're checking this is because it will add
                        # a FROM create_chatroom clause to the query, which we need
                        # for chatroom_id=create_chatroom_cte.c.id
                        # TODO: Figure out how to add a FROM for cte without adding it
                        #  to where (is this actually unsupported?)
                        create_chatroom_cte.c.id != -1,
                        tuple_(models.User.id, models.User.match_version).in_(
                            [
                                (user.id, user_match_version),
                                (match_user.id, match_user_match_version),
                            ]
                        ),
                    )
                    .values(
                        treatment=case(
                            [
                                (models.User.id == user.id, treatment.name),
                                (
                                    models.User.id == match_user.id,
                                    partner_treatment.name,
                                ),
                            ]
                        ).cast(models.User.treatment.type),
                        found_match_time=found_match_time,
                        chatroom_id=create_chatroom_cte.c.id,
                        # This is an implementation of optimistic concurrency control
                        match_version=uuid.uuid4().hex,
                    )
                    .returning(create_chatroom_cte.c.id)
                )

                # Actually run the query
                match_users = await access.session.execute(update_users_statement)

                # This will happen if either user's match_version has changed since
                # we started the transaction because we specify our known match_version
                # in the WHERE clause.
                # We raise an error here (one defined by
                # SQLAlchemy) to tell the session.begin() context manager's __aexit__
                # method to roll back the transaction.
                if match_users.rowcount != 2:
                    raise StaleDataError(
                        "User concurrently updated while attempting to match"
                    )

                # Get the chatroom ID returned from the query (RETURNING clause)
                chatroom_id = match_users.scalar()

                access.save_event(user.id, "create_chatroom", data=chatroom_id)
        except StaleDataError:
            logger.warning(
                format_parameterized_log_message(
                    "User attempted to match but version integrity check failed",
                    user_id=user_id,
                    partner_user_id=match_user_id,
                )
            )
            return

        # Refresh instance objects after committing them because otherwise they'll throw
        # all kinds of errors
        await access.session.refresh(user)
        await access.session.refresh(match_user)

        # Only log after a successful transaction
        logger.info(
            format_parameterized_log_message(
                "Found match for user, created chatroom",
                user_id=user.id,
                partner_user_id=match_user.id,
                chatroom_id=chatroom_id,
            )
        )
        logger.debug(
            format_parameterized_log_message(
                "Set treatment for user and matching user",
                user_id=user.id,
                partner_user_id=match_user.id,
                user_position=user.position.name.lower(),
                user_treatment=user.treatment.name.lower(),
                partner_position=match_user.position.name.lower(),
                partner_treatment=match_user.treatment.name.lower(),
                chatroom_id=chatroom_id,
            )
        )

        async with access.commit_after():
            # Send messages to both users
            for session_user, matched_with in zip(
                (user, match_user), (match_user, user)
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
            access.save_event(user.id, "leave_waiting_room", data=self._session_id)
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
        if (chatroom_id := self._user.chatroom_id) is not None and (
            partner := await access.other_user_in_chatroom(chatroom_id, self._user.id)
        ):
            return partner

    async def _update_partner_status(self, status) -> None:
        if not (partner := await self._partner()) or not partner.waiting_session_id:
            return

        await self._sio.emit("partner_status", status, partner.waiting_session_id)


# noinspection PyProtectedMember
socket_manager._sio.register_namespace(
    SessionSocketAsyncNamespace(WaitingRoomSocketSession, SOCKET_NAMESPACE_WAITING_ROOM)
)

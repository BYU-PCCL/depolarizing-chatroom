import React, {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import PageWidth from "../common/PageWidth";
import { io, Socket } from "socket.io-client";
import { useChatroom, useUser } from "../api/hooks";
import {
  BASE_URL,
  getAuthCode,
  getEndpointUrl,
  getRequestWithBodyHeaders,
} from "../api/apiUtils";
import { Message } from "./types";
import RephrasingsModal from "./RephrasingsModal";
import ChatMessageList from "../common/ChatMessageList";
import LeaveModal from "./LeaveModal";
import TypingIndicatorBubble from "../common/TypingIndicatorBubble";
import { useNavigate } from "react-router-dom";
import LoadingPage from "../common/LoadingPage";
import ErrorPage from "../common/ErrorPage";

const MemoizedChatMessageList = memo(ChatMessageList);

const THROTTLED_TYPING_INTERVAL = 6000;
const PARTNER_OFFLINE_TIMEOUT = 60_000;

function ChatroomPage() {
  const user = useUser();
  const chatroom = useChatroom();

  // Socket.IO object to communicate with the server
  const [socket, setSocket] = useState<Socket | undefined>();

  // This beautiful state trinity is all so that we can avoid React state
  // updates every time a user clicks a key
  const [hasComposingMessage, setHasComposingMessage] = useState(false);
  const composingElementRef = useRef<HTMLInputElement>(null);
  const composingTextRef = useRef<string | undefined>();

  // Message that is currently being sent but has not been sent—we prevent
  // the user from sending any more messages until this is cleared, which means
  // that it has been acknowledged by the server
  const [sendingMessage, setSendingMessage] = useState<string | undefined>();
  const [showingSendingMessage, setShowingSendingMessage] = useState(false);
  const sendingMessageTimeoutRef = useRef<NodeJS.Timeout | undefined>();

  // TODO: Why not consolidate these into one piece of state?
  // Original message from rephrasing response
  const [originalMessage, setOriginalMessage] = useState("");
  // Rephrasings from rephrasing response
  const [rephrasings, setRephrasings] = useState<
    { id: number; body: string }[]
  >([]);
  // Message ID received from rephrasing response that we'll need to respond with
  const [messageId, setMessageId] = useState<string | undefined>(undefined);

  // Whether the rephrasings modal is open—we also use this to prevent the user
  // from sending any more messages until the modal is closed
  const [showingRephrasingsModal, setShowingRephrasingsModal] = useState(false);
  // Whether the "leave early" modal is showing—this happens when the user
  // clicks the leave button before the turn limit is reached
  const [showingLeaveModal, setShowingLeaveModal] = useState(false);

  // Local state of all messages in the chatroom
  const [messages, setMessages] = useState<Message[]>([]);

  // Pushed from server: whether users have typed enough messages to go to
  // post-survey and get paid
  const [limitReached, setLimitReached] = useState<boolean>(false);
  // Pushed from server, delayed by client: Whether the partner has been offline
  // for at least n seconds
  const [partnerOnline, setPartnerOnline] = useState<boolean>(true);
  // Pushed from server: is other user typing?
  const [showingTypingBubble, setShowingTypingBubble] = useState(false);
  // This should really be pulled out of this class, but here we are. This lags
  // behind the actual typing state by 200ms just like the typing bubble
  const [showingTypingBubbleScrim, setShowingTypingBubbleScrim] =
    useState(false);

  // Timeout to hide the typing bubble if the other user hasn't sent a typing
  // event in a while
  const typingBubbleTimeoutRef = useRef<NodeJS.Timeout | undefined>();

  // State for throttling mechanism for us sending typing indicator events to
  // the server
  const typingTimeoutRef = useRef<NodeJS.Timeout | undefined>();
  const lastTypingTimeRef = useRef<number>(0);

  // Reference to timeout to wait n seconds before showing partner is offline
  // TODO: This logic should really be moved to the server, not something we
  //  should be doing on the client
  const partnerOfflineTimeoutRef = useRef<NodeJS.Timeout | undefined>();

  // Reference to interval to keep telling other user that we're typing while
  // the rephrasing modal is open
  // TODO: Should ALSO be moved to server
  const rephrasingsModalTypingIntervalRef = useRef<
    NodeJS.Timeout | undefined
  >();

  const chatMessagesElementLastScrollHeight = useRef<number | undefined>();
  // For some reason, we need to store this ref as a piece of state
  const [chatMessagesElement, setChatMessagesElement] = useState<
    HTMLDivElement | undefined
  >(undefined);
  // Reference to wrapper for tall (pre-overflow-scroll) chat messages wrapper
  // we use to transform for message-in animation
  const chatMessagesScrollWrapperElement = useRef<HTMLDivElement>(null);
  // Reference to performant (non-reloading) expanding gradient scrim at bottom
  // to give typing indicator contrast
  const typingIndicatorScrimRef = useRef<HTMLDivElement>(null);

  const navigate = useNavigate();

  // Chat message scrim listener
  const chatMessagesScrollListener = useCallback(() => {
    if (!chatMessagesElement || !typingIndicatorScrimRef.current) {
      return;
    }

    // Get distance from current scroll position to bottom, taking into account
    // offset
    const distanceFromBottom =
      chatMessagesElement.scrollHeight -
      chatMessagesElement.scrollTop -
      chatMessagesElement.offsetHeight;

    const scaleY = 1 + Math.min(1, distanceFromBottom / 100) * 2;
    typingIndicatorScrimRef.current.style.transform = `scaleY(${scaleY})`;
  }, [chatMessagesElement]);

  // Save ref to chat messages element
  const handleChatMessagesElement = useCallback(
    (node: HTMLDivElement) => {
      if (node === null) {
        return;
      }

      node.addEventListener("scroll", chatMessagesScrollListener);

      setChatMessagesElement(node);
    },
    [chatMessagesScrollListener]
  );

  const emitUserEvent = useCallback(
    (event: string, data?: any) => {
      if (!socket) {
        return;
      }

      socket.emit("event", {
        type: event,
        time: Date.now(),
        data,
      });
    },
    [socket]
  );

  const handlePartnerStatusChange = useCallback(
    (online: boolean) => {
      if (partnerOfflineTimeoutRef.current) {
        clearTimeout(partnerOfflineTimeoutRef.current);
        partnerOfflineTimeoutRef.current = undefined;
      }

      if (!online) {
        partnerOfflineTimeoutRef.current = setTimeout(() => {
          setPartnerOnline((status) => {
            if (status) {
              emitUserEvent("chatroom_display_partner_status", {
                online: false,
              });
            }
            return false;
          });
        }, PARTNER_OFFLINE_TIMEOUT);
      } else {
        setPartnerOnline((status) => {
          if (!status) {
            emitUserEvent("chatroom_display_partner_status", { online: true });
          }
          return true;
        });
      }
    },
    [emitUserEvent]
  );

  const handleReceiveMessage = useCallback(
    (message: any) => {
      if (user.data === undefined) {
        return;
      }

      if (message.user_id !== user.data.id) {
        // Mark partner as online if they send us a new message
        handlePartnerStatusChange(true);
        // Also hide the typing bubble
        setShowingTypingBubble(false);
      }
      setMessages((messages) => [
        ...messages,
        {
          body: message.message,
          time: Date.now(),
          state: message.user_id === user.data.id ? "sender" : "received",
        },
      ]);
    },
    [user.data, handlePartnerStatusChange]
  );

  const showTypingBubble = useCallback(() => {
    setShowingTypingBubble(true);
    if (typingBubbleTimeoutRef.current) {
      clearTimeout(typingBubbleTimeoutRef.current);
    }

    typingBubbleTimeoutRef.current = setTimeout(() => {
      setShowingTypingBubble(false);
    }, THROTTLED_TYPING_INTERVAL * 1.2);
  }, []);

  const handlePartnerTyping = useCallback(() => {
    showTypingBubble();
    handlePartnerStatusChange(true);
  }, [showTypingBubble, handlePartnerStatusChange]);

  // TODO: Generalize this to useThrottle or something
  // Based on throttle from underscore
  const sendThrottledTypingEvent = useCallback(() => {
    if (!socket) {
      return;
    }

    const throttleFunction = () => socket.emit("typing");

    const now = Date.now();
    const remaining =
      THROTTLED_TYPING_INTERVAL - (now - lastTypingTimeRef.current);
    if (remaining <= 0 || remaining > THROTTLED_TYPING_INTERVAL) {
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
        typingTimeoutRef.current = undefined;
      }
      lastTypingTimeRef.current = now;
      throttleFunction();
    } else if (typingTimeoutRef.current) {
      typingTimeoutRef.current = setTimeout(() => {
        lastTypingTimeRef.current = Date.now();
        typingTimeoutRef.current = undefined;
        throttleFunction();
      }, remaining);
    }
  }, [socket]);

  const handleComposeChange = useCallback(
    (value: string) => {
      if (!!composingTextRef?.current !== !!value) {
        setHasComposingMessage(!!value);
      }

      composingTextRef.current = value;
      sendThrottledTypingEvent();
    },
    [sendThrottledTypingEvent]
  );

  // Socket handling
  useEffect(() => {
    if (
      chatroom.isLoading ||
      chatroom.isError ||
      user.isLoading ||
      user.isError ||
      socket
    ) {
      // This is horrible but there are cases where the socket gets disconnected
      // so we just use this socket to reconnect
      if (socket && !socket.connected) {
        // And apparently only socket.io.connect works here
        socket.io.connect();
      }
      return;
    }

    setLimitReached(chatroom.data?.limitReached as boolean);

    const localSocket: Socket = io(
      getEndpointUrl("chatroom").replace("/api", ""),
      {
        // Unbelievable hack
        path: BASE_URL.endsWith("/api/")
          ? "/api/ws/socket.io"
          : "/ws/socket.io",
        auth: { token: getAuthCode() },
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: Infinity,
      }
    );
    setSocket(localSocket);
    localSocket.on("disconnect", function () {
      setTimeout(() => {
        console.debug("Attempting to reconnect to chatroom socket...");
        localSocket.connect();
      }, 5000);
    });
    localSocket.onAny((event: any, data: any) => console.debug(event, data));
    localSocket.on("min_limit_reached", () => {
      setLimitReached(true);
      emitUserEvent("chatroom_display_limit_reached", { limit_reached: true });
    });
    localSocket.on("rephrasings_status", (message: any) => {
      setSendingMessage((sendingMessage) => {
        if (message.will_attempt) {
          setShowingRephrasingsModal(true);
          setOriginalMessage(sendingMessage as string);
        }
        if (sendingMessageTimeoutRef.current) {
          clearTimeout(sendingMessageTimeoutRef.current);
        }
        setShowingSendingMessage(false);
        return undefined;
      });
    });
    localSocket.on("rephrasings_response", (message: any) => {
      setRephrasings(message.rephrasings);
      setMessageId(message.message_id);
    });
    localSocket.on("new_message", handleReceiveMessage);
    localSocket.on("typing", handlePartnerTyping);
    localSocket.on("messages", (messages: any) => {
      if (!user?.data?.id) {
        return;
      }
      setMessages(
        messages.map((message: any) => ({
          body: message.message,
          state: message.user_id === user.data.id ? "sender" : "received",
        }))
      );
    });
    localSocket.on("clear", () => setMessages([]));
    localSocket.on("redirect", ({ to }: { to: string }) => {
      if (to === "waiting") {
        navigate("/waiting");
      }
    });
  }, [
    handleReceiveMessage,
    chatroom.isLoading,
    chatroom.isError,
    user.isError,
    user.isLoading,
    chatroom.data,
    user.data,
    socket,
    handlePartnerTyping,
    showTypingBubble,
    handleComposeChange,
    handlePartnerStatusChange,
    emitUserEvent,
    navigate,
  ]);

  // Partner status handling (needs to be updated more quickly than other
  // socket handlers)
  useEffect(() => {
    if (
      chatroom.isLoading ||
      chatroom.isError ||
      user.isLoading ||
      user.isError ||
      !socket
    ) {
      return;
    }

    handlePartnerStatusChange(chatroom.data?.partnerOnline as boolean);

    socket.off("partner_status");
    socket.on("partner_status", handlePartnerStatusChange);
  }, [
    chatroom.isLoading,
    chatroom.isError,
    user.isError,
    user.isLoading,
    chatroom.data,
    user.data,
    socket,
    handlePartnerStatusChange,
  ]);

  // Reconnect socket on window focus
  useEffect(() => {
    const handleFocus = () => {
      if (!socket) {
        return;
      }
      if (!socket.connected) {
        socket.connect();
      }
      socket.emit("online");
      console.debug("Window online, sent partner online status");
    };

    window.addEventListener("focus", handleFocus);

    return () => window.removeEventListener("focus", handleFocus);
  }, [socket]);

  // Lag scrim visibility behind typing bubble visibility
  useEffect(() => {
    if (!showingTypingBubble) {
      const timeout = setTimeout(() => {
        setShowingTypingBubbleScrim(showingTypingBubble);
      }, 200);
      return () => clearTimeout(timeout);
    } else {
      setShowingTypingBubbleScrim(showingTypingBubble);
    }
  }, [showingTypingBubble]);

  // Emit typing event periodically if rephrasings modal is open
  useEffect(() => {
    if (showingRephrasingsModal) {
      rephrasingsModalTypingIntervalRef.current = setInterval(() => {
        if (socket) {
          socket.emit("typing");
        }
      }, 1000);
    }

    return () => {
      if (rephrasingsModalTypingIntervalRef.current) {
        clearInterval(rephrasingsModalTypingIntervalRef.current);
      }
    };
  }, [showingRephrasingsModal, socket]);

  const sendMessage = useCallback(() => {
    if (
      !socket ||
      !chatroom.data?.id ||
      sendingMessage ||
      showingRephrasingsModal ||
      showingLeaveModal ||
      !hasComposingMessage
    ) {
      return;
    }

    socket.emit("message", {
      body: composingElementRef.current?.value,
    });

    setSendingMessage(composingElementRef.current?.value);
    setHasComposingMessage(false);

    // This is really a horrible way to avoid state updates
    if (composingElementRef.current) {
      composingElementRef.current.value = "";
      handleComposeChange("");
    }

    sendingMessageTimeoutRef.current = setTimeout(() => {
      setShowingSendingMessage(true);
    }, 500);
  }, [
    socket,
    hasComposingMessage,
    handleComposeChange,
    chatroom.data,
    sendingMessage,
    showingRephrasingsModal,
    showingLeaveModal,
  ]);

  const sendRephrasingResponse = useCallback(
    (body: string, rephrasingIndex?: number | undefined) => {
      if (!socket || !chatroom.data?.id || !messageId) {
        return;
      }

      socket.emit("rephrasing_response", {
        message_id: messageId,
        rephrasing_id:
          rephrasingIndex !== undefined
            ? rephrasings[rephrasingIndex].id
            : undefined,
        body,
      });

      setShowingRephrasingsModal(false);
      setRephrasings([]);
      setOriginalMessage("");
      setMessageId(undefined);
    },
    [socket, chatroom.data, messageId, rephrasings]
  );

  const handleInputKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === "Enter") {
        event.preventDefault();
        sendMessage();
      }
    },
    [sendMessage]
  );

  const handleLeave = useCallback(
    async (reason?: string) => {
      // Navigate to user.post_survey_url
      if (!user?.data?.post_survey_url) {
        return;
      }

      emitUserEvent("chatroom_leave", {
        provided_reason: !!reason,
        limit_reached: limitReached,
        partner_online: partnerOnline,
      });
      if (reason) {
        await fetch(getEndpointUrl("user"), {
          method: "PUT",
          headers: getRequestWithBodyHeaders(),
          body: JSON.stringify({ leaveReason: reason }),
        });
      }

      window.location.href = user.data.post_survey_url as string;
    },
    [emitUserEvent, limitReached, partnerOnline, user.data?.post_survey_url]
  );

  const handleLeaveClicked = useCallback(() => {
    if (limitReached || !partnerOnline) {
      handleLeave();
    } else {
      setShowingLeaveModal(true);
      emitUserEvent("chatroom_open_leave_dialog");
    }
  }, [handleLeave, limitReached, partnerOnline, emitUserEvent]);

  useLayoutEffect(() => {
    if (!chatMessagesElement || !chatMessagesScrollWrapperElement.current) {
      return;
    }

    const { scrollHeight, scrollTop, offsetHeight } = chatMessagesElement;
    const lastScrollHeight =
      chatMessagesElementLastScrollHeight?.current ?? scrollHeight;
    const distanceFromBottom = lastScrollHeight - scrollTop - offsetHeight;
    const scrollDifference = scrollHeight - lastScrollHeight;
    chatMessagesElementLastScrollHeight.current = scrollHeight;

    if (scrollDifference === 0 || distanceFromBottom > 100) {
      // Attempt to do this again with a reload, assuming we haven't already
      return;
    }

    // Scroll to the bottom
    chatMessagesElement.scrollTo({
      top: scrollHeight,
    });
    // Transform the scroll wrapper element to match the scroll position
    // of the chat messages element
    const elementRef = chatMessagesScrollWrapperElement.current;
    elementRef.style.transitionDuration = "0s";
    // void elementRef.offsetWidth;
    elementRef.style.transform = `translateY(${scrollDifference}px)`;
    void elementRef.offsetWidth;
    // Add "transition-transform" class to the scroll wrapper element to
    // animate the transform
    elementRef.classList.add("transition-transform");
    elementRef.style.transitionDuration = "300ms";
    // Set the transform to 0 to reset the scroll wrapper element
    // The previous line is needed to force a reflow
    elementRef.style.transform = "translateY(0)";
    // Remove the "transition-transform" class to the scroll wrapper element
    // to avoid animating the transform when the user scrolls
    elementRef.classList.remove("transition-transform");
    // Add a scroll listener back after a short delay
  }, [chatMessagesElement, messages, showingSendingMessage]);

  if (user.isLoading || chatroom.isLoading) {
    return <LoadingPage />;
  }

  if (user.isError || chatroom.isError) {
    return (
      <ErrorPage
        error={(user.isError ? user : chatroom)?.error?.message || ""}
      />
    );
  }

  return (
    <PageWidth>
      <div className="mb-4 w-full">
        <div className="mb-1 sm:mb-8 w-full flex flex-wrap justify-between items-center gap-4">
          <div className="flex gap-4 w-full justify-between items-center">
            <h1 className="text-3xl sm:text-4xl">
              Gun Control in America: More or Less?
            </h1>
            <button
              className={
                "transition bg-gray-300 hover:bg-gray-400 active:bg-gray-500 text-black font-bold py-2 px-4 -mb-1 rounded whitespace-nowrap" +
                (limitReached || !partnerOnline
                  ? " bg-green-300 hover:bg-green-400 active:bg-green-500"
                  : " bg-gray-300 hover:bg-gray-400 active:bg-red-500")
              }
              onClick={handleLeaveClicked}
            >
              {limitReached || !partnerOnline ? "Finish" : "Quit Early"}
            </button>
          </div>
        </div>
        {limitReached && partnerOnline && (
          <div className="flex flex-col gap-2 -mx-4 sm:mx-0 p-3 px-4 bg-green-200 sm:rounded-lg mt-4 sm:-mt-5 text-sm sm:text-base">
            <p>
              <b>
                You’ve now talked with your partner long enough to move on to
                the final survey.
              </b>{" "}
              When you would like to end your conversation and go to that
              survey, click <b>finish</b>. You are also welcome to continue
              talking with your partner.
            </p>
          </div>
        )}
        {!partnerOnline && (
          <div className="flex flex-col gap-2 -mx-4 sm:mx-0 p-3 px-4 bg-green-200 sm:rounded-lg mt-4 sm:-mt-5 text-sm sm:text-base">
            <p>
              <b>Your partner has left the chat.</b> Click <b>finish</b> to
              continue to the last survey and receive your payment.
            </p>
          </div>
        )}
      </div>
      <div className="flex -mx-4 -mb-4 sm:mx-0 sm:mb-0 p-3 sm:p-8 border-t sm:border border-gray-300 sm:rounded-2xl w-[calc(100%_+_2rem)] sm:w-full grow flex-col bg-white">
        <div className="flex rounded-2xl flex-1 flex-col w-full h-full relative">
          <div
            className="flex-1 basis-0 overflow-scroll px-4 -mx-4 -my-3 pt-3 mb-0 pb-0 sm:pt-9 sm:-my-8 sm:px-7 sm:-mx-7 sm:mb-0"
            ref={handleChatMessagesElement}
          >
            <div className="overflow-clip">
              <div
                ref={chatMessagesScrollWrapperElement}
                className="ease-[cubic-bezier(0.03, 0.55, 0.2, 1)]"
              >
                <MemoizedChatMessageList
                  messages={messages}
                  showTimes={false}
                  sendingMessage={
                    showingSendingMessage ? sendingMessage : undefined
                  }
                />
              </div>
            </div>
          </div>
          <div className="absolute bottom-0 pointer-events-none w-full">
            <div
              className={
                "w-full bg-gradient-to-t from-white w-full h-full absolute bottom-0 origin-bottom transition ease-out" +
                (showingTypingBubbleScrim ? " opacity-1" : " opacity-0")
              }
              ref={typingIndicatorScrimRef}
            ></div>
            <div className="mb-2.5">
              <TypingIndicatorBubble visible={showingTypingBubble} />
            </div>
          </div>
        </div>
        <div className="border-t pt-3 sm:pt-6 w-full flex gap-4">
          <input
            className="border border-gray-300 rounded-md flex-1 px-3"
            onChange={(event) => handleComposeChange(event.target.value)}
            onKeyDown={handleInputKeyDown}
            ref={composingElementRef}
            placeholder={
              sendingMessage === undefined
                ? "Type a message"
                : "Sending message..."
            }
            size={1}
          ></input>
          <button
            className="rounded-full bg-blue-600 px-3.5 text-center hover:bg-blue-500 active:bg-blue-400 disabled:opacity-60 disabled:pointer-events-none transition"
            onClick={sendMessage}
            disabled={
              !hasComposingMessage ||
              sendingMessage !== undefined ||
              showingRephrasingsModal ||
              showingLeaveModal
            }
          >
            {!showingSendingMessage &&
            !showingRephrasingsModal &&
            !showingLeaveModal ? (
              <span
                role="button"
                className="material-icons select-none p-1.5 text-white text-2xl"
              >
                send
              </span>
            ) : (
              <svg
                role="status"
                className="inline w-6 h-6 my-2.5 mx-1.5 text-transparent animate-spin fill-white"
                viewBox="0 0 100 101"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z"
                  fill="currentColor"
                />
                <path
                  d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z"
                  fill="currentFill"
                />
              </svg>
            )}
          </button>
        </div>
      </div>
      <LeaveModal
        isOpen={showingLeaveModal}
        onCancel={() => setShowingLeaveModal(false)}
        onConfirm={(reason: string) => {
          setShowingLeaveModal(false);
          handleLeave(reason);
        }}
      />
      <RephrasingsModal
        isOpen={showingRephrasingsModal}
        original={originalMessage}
        rephrasings={rephrasings.map((rephrasing) => rephrasing.body)}
        onSendOriginal={sendRephrasingResponse}
        onSendRephrasing={sendRephrasingResponse}
      />
    </PageWidth>
  );
}

export default ChatroomPage;

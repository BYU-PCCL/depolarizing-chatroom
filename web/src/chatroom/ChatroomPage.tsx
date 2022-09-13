import React, { useCallback, useEffect, useRef, useState } from "react";
import PageWidth from "../common/PageWidth";
import socketIOClient, { Socket } from "socket.io-client";
import { useChatroom, useUser } from "../api/hooks";
import { BASE_URL, getAuthCode, getEndpointUrl } from "../api/apiUtils";
import { Message } from "./types";
import RephrasingsModal from "./RephrasingsModal";
import ChatMessageList from "../common/ChatMessageList";
import LeaveModal from "./LeaveModal";
import TypingIndicatorBubble from "../common/TypingIndicatorBubble";
import { useNavigate } from "react-router-dom";

function ChatroomPage() {
  const user = useUser();
  const chatroom = useChatroom();
  const [socket, setSocket] = useState<Socket | undefined>();
  const [composingMessage, setComposingMessage] = useState("");
  const [showingRephrasingsModal, setShowingRephrasingsModal] = useState(false);
  const [showingLeaveModal, setShowingLeaveModal] = useState(false);
  const [originalMessage, setOriginalMessage] = useState("");
  const [rephrasings, setRephrasings] = useState<
    { id: number; body: string }[]
  >([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messageId, setMessageId] = useState<string | undefined>(undefined);
  const [limitReached, setLimitReached] = useState<boolean>(false);
  const [showingTypingBubble, setShowingTypingBubble] = useState(false);
  const navigate = useNavigate();

  const typingIndicatorScrim = useRef<HTMLDivElement>(null);
  const chatMessagesElement = useRef<HTMLDivElement>(null);

  const typingBubbleTimeoutRef = useRef<NodeJS.Timeout | undefined>();
  const typingTimeoutRef = useRef<NodeJS.Timeout | undefined>();
  const rephrasingsModalTypingIntervalRef = useRef<
    NodeJS.Timeout | undefined
  >();
  const lastTypingTimeRef = useRef<number>(0);

  const chatMessagesScrollListener = useCallback(() => {
    if (!chatMessagesElement.current || !typingIndicatorScrim.current) {
      return;
    }

    // Get distance from current scroll position to bottom, taking into account
    // offset
    const distanceFromBottom =
      chatMessagesElement.current.scrollHeight -
      chatMessagesElement.current.scrollTop -
      chatMessagesElement.current.offsetHeight;

    const scaleY = 1 + Math.min(1, distanceFromBottom / 100) * 2;
    typingIndicatorScrim.current.style.transform = `scaleY(${scaleY})`;
  }, []);

  useEffect(() => {
    if (!typingIndicatorScrim.current || !chatMessagesElement.current) {
      return;
    }

    chatMessagesElement.current.addEventListener(
      "scroll",
      chatMessagesScrollListener
    );

    const elementRef = chatMessagesElement.current;

    return () => {
      elementRef.removeEventListener("scroll", chatMessagesScrollListener);
    };
  }, [chatMessagesScrollListener]);

  const addMessage = useCallback(
    (message: any) => {
      if (user.data === undefined) {
        return;
      }

      setShowingTypingBubble(false);
      setMessages((messages) => [
        ...messages,
        {
          body: message.message,
          time: Date.now(),
          isSender: message.user_id === user.data.id,
        },
      ]);
    },
    [user]
  );

  const showTypingBubble = useCallback(() => {
    setShowingTypingBubble(true);
    if (typingBubbleTimeoutRef.current) {
      clearTimeout(typingBubbleTimeoutRef.current);
    }
    const typingBubbleTimeout = setTimeout(() => {
      setShowingTypingBubble(false);
    }, 1200);
    typingBubbleTimeoutRef.current = typingBubbleTimeout;
    return () => {
      clearTimeout(typingBubbleTimeout);
      setShowingTypingBubble(false);
    };
  }, []);

  useEffect(() => {
    if (
      chatroom.isLoading ||
      chatroom.isError ||
      user.isLoading ||
      user.isError ||
      socket
    ) {
      return;
    }

    const localSocket: Socket = socketIOClient(
      getEndpointUrl("chatroom").replace("/api", ""),
      {
        // Unbelievable hack
        path: BASE_URL.endsWith("/api/")
          ? "/api/ws/socket.io"
          : "/ws/socket.io",
        auth: { token: getAuthCode() },
      }
    );
    localSocket.onAny((event: any, data: any) => console.debug(event, data));
    localSocket.on("min_limit_reached", () => {
      setLimitReached(true);
    });
    localSocket.on("rephrasings_status", (message: any) => {
      setComposingMessage((composingMessage) => {
        if (message.will_attempt) {
          setShowingRephrasingsModal(true);
          setOriginalMessage(composingMessage);
        }
        return "";
      });
    });
    localSocket.on("rephrasings_response", (message: any) => {
      setRephrasings(message.rephrasings);
      setMessageId(message.message_id);
    });
    localSocket.on("new_message", addMessage);
    localSocket.on("typing", showTypingBubble);
    localSocket.on("messages", (messages: any) => {
      if (!user?.data?.id) {
        return;
      }
      setMessages(
        messages.map((message: any) => ({
          body: message.message,
          isSender: message.user_id === user.data.id,
        }))
      );
    });
    localSocket.on("clear", () => {
      setMessages([]);
    });
    localSocket.on("redirect", ({ to }: { to: string }) => {
      if (to === "waiting") {
        navigate("/waiting");
      }
    });
    setSocket(localSocket);
  }, [addMessage, chatroom, user, socket]);

  useEffect(() => {
    if (rephrasingsModalTypingIntervalRef.current) {
      clearInterval(rephrasingsModalTypingIntervalRef.current);
    }

    if (showingRephrasingsModal) {
      rephrasingsModalTypingIntervalRef.current = setInterval(() => {
        if (socket) {
          socket.emit("typing");
        }
      }, 500);
    }
  }, [showingRephrasingsModal, socket]);

  const sendMessage = useCallback(() => {
    // @ts-ignore
    if (!socket || !chatroom.data.id) {
      return;
    }

    // Note that we do NOT empty the composing message field here because we
    // want it to hang around for the rephrasings modal
    socket.emit("message", {
      body: composingMessage,
    });
  }, [socket, composingMessage, chatroom]);

  const sendRephrasingResponse = useCallback(
    (body: string, rephrasingIndex?: number | undefined) => {
      // @ts-ignore
      if (!socket || !chatroom.data.id || !messageId) {
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
    [socket, chatroom, messageId, rephrasings]
  );

  const restartChat = useCallback(() => {
    // @ts-ignore
    if (!socket || !chatroom.data.id) {
      return;
    }

    socket.emit("clear");
  }, [chatroom?.data?.id, socket]);

  const handleInputKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === "Enter") {
        event.preventDefault();
        sendMessage();
      }
    },
    [sendMessage]
  );

  const handleComposeChange = useCallback(
    (value: string) => {
      setComposingMessage(value);

      if (!socket) {
        return;
      }

      const now = Date.now();
      if (now > lastTypingTimeRef.current + 800) {
        lastTypingTimeRef.current = now;
        socket.emit("typing");
        return;
      }
      const timeUntilNextTyping = lastTypingTimeRef.current + 800 - now;

      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }

      const typingTimeout = setTimeout(() => {
        socket.emit("typing");
      }, timeUntilNextTyping);

      typingTimeoutRef.current = typingTimeout;

      return () => clearTimeout(typingTimeout);
    },
    [socket]
  );

  const handleLeave = useCallback(() => {
    // Navigate to user.post_survey_url
    if (!user?.data?.post_survey_url) {
      return;
    }

    window.location.href = user.data.post_survey_url as string;
  }, [user.data]);

  const handleLeaveClicked = useCallback(() => {
    if (limitReached) {
      handleLeave();
    } else {
      setShowingLeaveModal(true);
    }
  }, [handleLeave, limitReached]);

  useEffect(() => {
    if (chatMessagesElement.current) {
      chatMessagesElement.current.scrollTo({
        top: chatMessagesElement.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages]);

  if (user.isLoading || chatroom.isLoading) {
    return <div>Loading...</div>;
  }

  if (user.isError || chatroom.isError) {
    // @ts-ignore
    return <div>Error: {(user.isError ? user : chatroom).error.message}</div>;
  }

  // @ts-ignore
  const prompt: string = chatroom.data.prompt;
  // @ts-ignore
  const position: string = user.data.position;
  // @ts-ignore
  const roomId: number = chatroom.data.id;

  return (
    <PageWidth>
      <div className="mb-4 w-full">
        <div className="mb-2 sm:mb-10 w-full flex flex-wrap justify-between items-center gap-4">
          {/*<h1 className="text-4xl">{prompt}</h1>*/}
          <h1 className="text-4xl">Gun Control in America: More or Less?</h1>
          <div className="flex gap-3">
            <button
              className="transition bg-gray-300 hover:bg-gray-400 active:bg-gray-500 text-black font-bold py-2 px-4 rounded"
              onClick={restartChat}
            >
              Restart
            </button>
            <button
              className={
                "transition bg-gray-300 hover:bg-gray-400 active:bg-gray-500 text-black font-bold py-2 px-4 rounded" +
                (limitReached
                  ? " bg-green-300 hover:bg-green-400 active:bg-green-500"
                  : " bg-gray-300 hover:bg-gray-400 active:bg-red-500")
              }
              onClick={handleLeaveClicked}
            >
              {limitReached ? "Finish" : "Leave"}
            </button>
          </div>
        </div>
        {limitReached && (
          <div className="flex flex-col gap-2 p-3 bg-green-200 rounded-lg mt-4 sm:-mt-6">
            <p>
              You’ve now talked with your partner long enough to move on to the
              final survey. When you would like to end your conversation and go
              to that survey, click <b>finish</b>. You are also welcome to
              continue talking with your partner.
            </p>
          </div>
        )}
      </div>
      <div className="flex p-8 border border-gray-300 rounded-xl flex-1 flex-col w-full bg-white">
        <div className="flex rounded-xl flex-1 flex-col w-full h-full relative">
          <div
            className="flex-1 basis-0 overflow-scroll py-9 -my-8 px-7 -mx-7 mb-0"
            ref={chatMessagesElement}
          >
            <ChatMessageList messages={messages} showTimes={false} />
          </div>
          <div className="absolute bottom-0 pointer-events-none w-full">
            <div
              className="w-full bg-gradient-to-t from-white w-full h-full absolute bottom-0 origin-bottom"
              ref={typingIndicatorScrim}
            ></div>
            <div className="mb-2.5">
              <TypingIndicatorBubble visible={showingTypingBubble} />
            </div>
          </div>
        </div>
        <div className="border-t pt-5 w-full flex gap-4">
          <input
            className="border border-gray-300 rounded-md flex-1 px-3"
            value={composingMessage}
            onChange={(event) => handleComposeChange(event.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder="Type a message"
          ></input>
          <button
            className="rounded-full bg-blue-600 px-3.5 text-center drop-shadow-md hover:bg-blue-500 active:bg-blue-400 disabled:opacity-60 disabled:pointer-events-none transition"
            onClick={sendMessage}
            disabled={!composingMessage}
          >
            <span
              role="button"
              className="material-icons select-none p-2 text-white text-2xl"
            >
              send
            </span>
          </button>
        </div>
      </div>
      <LeaveModal
        isOpen={showingLeaveModal}
        onCancel={() => setShowingLeaveModal(false)}
        onConfirm={(reason: string) => {
          setShowingLeaveModal(false);
          handleLeave();
          // TODO: Also redirect somewhere
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

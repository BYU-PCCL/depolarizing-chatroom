import React, { useCallback, useEffect, useState } from "react";
import PageWidth from "../common/PageWidth";
import socketIOClient, { Socket } from "socket.io-client";
import { useChatroom, useUser } from "../api/hooks";
import { BASE_URL, getAuthCode, getEndpointUrl } from "../api/apiUtils";
import { Message } from "./types";
import RephrasingsModal from "./RephrasingsModal";
import ChatMessageList from "../common/ChatMessageList";
import LeaveModal from "./LeaveModal";

function ChatroomPage() {
  const user = useUser();
  const chatroom = useChatroom();
  const [socket, setSocket] = useState<Socket | undefined>();
  const [composingMessage, setComposingMessage] = useState("");
  const [showingRephrasingsModal, setShowingRephrasingsModal] = useState(false);
  const [showingLeaveModal, setShowingLeaveModal] = useState(false);
  const [originalMessage, setOriginalMessage] = useState("");
  const [rephrasings, setRephrasings] = useState<Record<number, string>>({});
  const [messages, setMessages] = useState<Message[]>([]);
  const [messageId, setMessageId] = useState<string | undefined>(undefined);
  const showTimes = false;

  const addMessage = useCallback(
    (message: any) => {
      if (user.data === undefined) {
        return;
      }

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
    setSocket(localSocket);
  }, [addMessage, chatroom, user, socket]);

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
            ? Object.keys(rephrasings)[rephrasingIndex]
            : undefined,
        body,
      });

      setShowingRephrasingsModal(false);
      setRephrasings({});
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
      <div className="mb-6 sm:mb-10 w-full">
        <div className="mb-4 w-full flex flex-wrap justify-between items-center gap-4">
          <h1 className="text-4xl">{prompt}</h1>
          <div className="flex gap-3">
            <button
              className="transition bg-gray-300 hover:bg-gray-400 active:bg-gray-500 text-black font-bold py-2 px-4 rounded"
              onClick={restartChat}
            >
              Restart
            </button>
            <button
              className="transition bg-gray-300 hover:bg-gray-400 active:bg-gray-500 text-black font-bold py-2 px-4 rounded"
              onClick={() => setShowingLeaveModal(true)}
            >
              Leave
            </button>
          </div>
        </div>
      </div>
      <div className="flex p-8 border border-gray-300 rounded-xl flex-1 flex-col w-full bg-white">
        <div className="flex-1 basis-0 overflow-scroll py-8 -my-8 px-7 -mx-7 mb-0">
          <ChatMessageList messages={messages} showTimes={false} />
        </div>
        <div className="border-t pt-5 w-full flex gap-4">
          <input
            className="border border-gray-300 rounded-md flex-1 px-3"
            value={composingMessage}
            onChange={(event) => setComposingMessage(event.target.value)}
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
          // TODO: Also redirect somewhere
        }}
      />
      <RephrasingsModal
        isOpen={showingRephrasingsModal}
        original={originalMessage}
        rephrasings={Object.values(rephrasings)}
        onSendOriginal={sendRephrasingResponse}
        onSendRephrasing={sendRephrasingResponse}
      />
    </PageWidth>
  );
}

export default ChatroomPage;

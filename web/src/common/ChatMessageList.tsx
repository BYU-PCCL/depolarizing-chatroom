import ChatMessage, { ChatMessageState, ClusterPosition } from "./ChatMessage";
import { memo, useEffect, useRef } from "react";
import "./ellipsis.css";

// This should be moved somewhere else
interface Message {
  body: string;
  state: ChatMessageState;
  time?: number;
}

const MemoizedChatMessage = memo(ChatMessage);

function ChatMessageList({
  messages,
  // This really shouldn't be here, but it's a quick fix
  sendingMessage,
  showTimes = true,
}: {
  messages: Message[];
  sendingMessage?: string;
  showTimes?: boolean;
}) {
  const scrollElement = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollElement.current) {
      scrollElement.current.scrollTop = scrollElement.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div
      className="w-full flex flex-col overflow-clip pb-9"
      ref={scrollElement}
      data-test-id="chat-messages"
    >
      {messages.map((message, index, array) => {
        let clusterPosition;
        // Get last message and next message or undefined
        const lastMessage = index > 0 ? array[index - 1] : undefined;
        const nextMessage =
          index < array.length - 1 ? array[index + 1] : undefined;
        const sameAsLastMessage =
          lastMessage && lastMessage.state === message.state;
        const sameAsNextMessage =
          (nextMessage && nextMessage.state === message.state) ||
          (nextMessage === undefined &&
            sendingMessage &&
            message.state === "sender");

        if (!sameAsLastMessage && !sameAsNextMessage) {
          clusterPosition = "single";
        } else if (sameAsLastMessage && !sameAsNextMessage) {
          clusterPosition = "last";
        } else if (!sameAsLastMessage && sameAsNextMessage) {
          clusterPosition = "first";
        } else if (sameAsLastMessage && sameAsNextMessage) {
          clusterPosition = "after";
        }

        return (
          <MemoizedChatMessage
            key={index}
            body={message.body}
            time={showTimes ? message.time : undefined}
            state={message.state}
            last={index === messages.length - 1 && !sendingMessage}
            clusterPosition={(clusterPosition || "first") as ClusterPosition}
          />
        );
      })}
      {sendingMessage && (
        <div className="animate-chat-message animate-chat-sent">
          <MemoizedChatMessage
            body={sendingMessage}
            state={"sending"}
            clusterPosition={
              messages.length > 0 &&
              messages[messages.length - 1].state === "sender"
                ? "after"
                : "first"
            }
          />
          <div className="w-full flex flex-col items-end inline-block">
            <p className="text-sm text-blue-600 ellipsis">
              Sending<span>.</span>
              <span>.</span>
              <span>.</span>
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default ChatMessageList;

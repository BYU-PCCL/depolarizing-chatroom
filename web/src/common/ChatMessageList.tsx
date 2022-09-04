import ChatMessage from "./ChatMessage";
import { useEffect, useRef } from "react";

function ChatMessageList({
  messages,
  showTimes = true,
}: {
  messages: {
    body: string;
    time?: number;
    tutorial?: boolean;
    isSender: boolean;
  }[];
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
      className="w-full flex flex-col overflow-scroll"
      ref={scrollElement}
      data-test-id="chat-messages"
    >
      {messages.map((message, index) => (
        <ChatMessage
          key={index}
          body={message.body}
          time={showTimes ? message.time : undefined}
          tutorial={message.tutorial}
          isSender={message.isSender}
        />
      ))}
    </div>
  );
}

export default ChatMessageList;

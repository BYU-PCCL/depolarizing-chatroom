import { useCallback, useEffect, useState } from "react";
// @ts-ignore
import RelativeTime from "@yaireo/relative-time";
import { useInterval } from "../hooks";
import "./message-animation.css";

const relativeTime = new RelativeTime();

export type ChatMessageState = "sender" | "sending" | "received" | "tutorial";
export type ClusterPosition = "first" | "after" | "last" | "single";

function ChatMessage({
  body,
  state,
  clusterPosition = "first",
  time = undefined,
  last = false,
}: {
  body: string;
  state: ChatMessageState;
  clusterPosition?: ClusterPosition;
  time?: number;
  last?: boolean;
}) {
  const [formattedDate, setFormattedDate] = useState<string | undefined>(
    undefined
  );

  const updateRelativeTime = useCallback(() => {
    if (!time) {
      return;
    }

    setFormattedDate(relativeTime.from(new Date(time)));
  }, [time]);

  useEffect(() => {
    updateRelativeTime();
  }, [time, updateRelativeTime]);

  useInterval(() => {
    updateRelativeTime();
  }, 20000);

  let className;

  if (state === "sender") {
    let roundedness;
    if (clusterPosition === "first" || clusterPosition === "single") {
      roundedness = "rounded-br-sm";
    } else if (clusterPosition === "after" || clusterPosition === "last") {
      roundedness = "rounded-br-sm rounded-tr-sm";
    }
    className = `text-white bg-blue-600 max-w-[80%] animate-chat-sent ${roundedness}`;
  } else if (state === "sending") {
    // TODO: Fix code duplication
    let roundedness;
    if (clusterPosition === "first" || clusterPosition === "single") {
      roundedness = "rounded-br-sm";
    } else if (clusterPosition === "after" || clusterPosition === "last") {
      roundedness = "rounded-br-sm rounded-tr-sm";
    }
    className = `border bg-blue-200 border-blue-600 max-w-[80%] ${roundedness}`;
  } else if (state === "received") {
    let roundedness;
    if (clusterPosition === "first" || clusterPosition === "single") {
      roundedness = "rounded-bl-sm";
    } else if (clusterPosition === "after" || clusterPosition === "last") {
      roundedness = "rounded-bl-sm rounded-tl-sm";
    }
    className = `bg-gray-200 max-w-[80%] animate-chat-received ${roundedness}`;
  } else if (state === "tutorial") {
    className = "border border-green-600 bg-green-200";
  }

  if (last) {
    className += " animate-chat-message";
  }

  return (
    <div
      className={
        "w-full flex flex-col " +
        (clusterPosition === "last" || clusterPosition === "single"
          ? "mb-3 "
          : "mb-[0.15em] ") +
        (state === "sender" || state === "sending"
          ? "items-end"
          : "items-start")
      }
    >
      <div className={"px-4 py-2 rounded-xl overflow-clip " + className}>
        {body}
      </div>
      {formattedDate && (
        <span className="text-gray-500 -mb-1 text-sm">{formattedDate}</span>
      )}
    </div>
  );
}

export default ChatMessage;

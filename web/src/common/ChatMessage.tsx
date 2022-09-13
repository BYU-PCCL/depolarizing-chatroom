import { useCallback, useEffect, useState } from "react";
// @ts-ignore
import RelativeTime from "@yaireo/relative-time";
import { useInterval } from "../hooks";

const relativeTime = new RelativeTime();

function ChatMessage({
  body,
  isSender,
  time = undefined,
  tutorial = false,
}: {
  body: string;
  time?: number;
  isSender: boolean;
  tutorial?: boolean;
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
  }, [time]);

  useInterval(() => {
    updateRelativeTime();
  }, 20000);

  return (
    <div
      className={
        "w-full flex flex-col mb-3 " + (isSender ? "items-end" : "items-start")
      }
    >
      <div
        className={
          "px-4 py-2 rounded-xl " +
          (isSender
            ? "rounded-br-none text-white bg-blue-600"
            : (tutorial ? "border bg-green-100 border-green-600" : "bg-gray-200 rounded-bl-none"))
        }
      >
        {body}
      </div>
      {formattedDate && (
        <span className="text-gray-500 -mb-1 text-sm">{formattedDate}</span>
      )}
    </div>
  );
}

export default ChatMessage;

import ContentEditable, { ContentEditableEvent } from "react-contenteditable";
import { useCallback, useEffect, useRef, useState } from "react";
import he from "he";

function ComposeMessage({
  body,
  onChange = () => {},
  onSend = () => {},
  colors = ["blue-400", "blue-500", "blue-600"],
}: {
  body: string;
  onChange?: (body: string) => void;
  onSend?: (body: string) => void;
  colors?: string[];
}) {
  const contentEditableRef = useRef<HTMLDivElement>(null);
  const [editedBody, setEditedBody] = useState(body);

  useEffect(() => {
    setEditedBody(body);
  }, [body]);

  const cleanContent = useCallback((data: string) => {
    return he.decode(data.replace("<br>", "\n").replace(/<[^>]*>/g, "") ?? "");
  }, []);

  const handleChange = useCallback(
    (event: ContentEditableEvent) => {
      const newBody = cleanContent(event.target.value);
      setEditedBody(event.target.value);
      onChange(newBody);
    },
    [cleanContent, onChange]
  );

  return (
    <div className="flex items-center gap-3 sm:gap-6">
      <div
        className={`flex grow border-2 rounded-xl rounded-br-sm border-${colors[2]} text-${colors[2]} max-h-32 sm:max-h-[initial] overflow-scroll`}
      >
        <ContentEditable
          className={`transition py-1.5 px-3 sm:py-3 sm:px-4 rounded-xl rounded-br-sm flex-1 border-${colors[2]} text-${colors[2]} outline-none`}
          innerRef={contentEditableRef}
          html={editedBody}
          disabled={false}
          onChange={handleChange}
        />
      </div>
      <button
        className={`transition rounded-full border-2 px-3 text-center transition select-none border-${colors[2]} text-${colors[2]} hover:text-${colors[1]} active:text-${colors[0]} hover:border-${colors[1]} active:border-${colors[0]}`}
        onClick={() => onSend(cleanContent(editedBody))}
      >
        <span
          role="button"
          className="material-icons text-xl px-1 py-0.5 sm:text-2xl sm:py-1 sm:px-2"
        >
          send
        </span>
      </button>
    </div>
  );
}

export default ComposeMessage;

import React, { useRef, useState } from "react";
import ContentEditable from "react-contenteditable";
import he from "he";

function EditableChatMessage({
  data: { body, position, visible },
  onChange = () => {},
  onDelete = () => {},
}: {
  data: { body: string; position: "oppose" | "support"; visible: boolean };
  onChange?: (value: {
    body: string;
    position: "oppose" | "support";
    visible: boolean;
  }) => void;
  onDelete?: () => void;
}) {
  const contentEditableRef = useRef<HTMLDivElement>(null);
  // Replace newlines that are not followed by newlines with a <br>
  const [editedBody, setEditedBody] = useState(
    // Replace
    body.replace(/\n(?!\n)/g, "<br>")
  );
  return (
    <div className={"w-full flex flex-col mb-1"}>
      <div className="flex items-center justify-between w-full gap-1">
        <div
          className={
            "px-3 py-2 rounded-xl rounded-br-none flex items-center transition flex-1 text-sm " +
            (position === "support" ? "bg-blue-200" : "bg-red-200") +
            (visible ? "" : " opacity-50")
          }
        >
          <ContentEditable
            innerRef={contentEditableRef}
            html={editedBody}
            disabled={false}
            className="w-full"
            onChange={(event) => {
              onChange({
                body: he.decode(
                  contentEditableRef?.current?.innerText
                    .replace("<br>", "\n")
                    .replace(/<[^>]*>/g, "") ?? ""
                ),
                position,
                visible,
              });
              setEditedBody(event.target.value);
            }}
          />
        </div>
      </div>
      <div className={"w-full flex justify-between pt-1 items-center"}>
        <div className="flex gap-1.5">
          <span
            role="button"
            className="material-icons select-none transition text-slate-400 hover:text-slate-500"
            onClick={onDelete}
          >
            delete
          </span>
          <span
            role="button"
            onClick={() => {
              onChange({ body, position, visible: !visible });
            }}
            className={
              "material-icons select-none transition " +
              (visible
                ? "text-slate-400 hover:text-slate-500"
                : "text-slate-600 hover:text-slate-700")
            }
          >
            {visible ? "visibility" : "visibility_off"}
          </span>
        </div>
        <div
          className={"flex gap-1 items-center" + (visible ? "" : " opacity-50")}
        >
          <span
            role="button"
            onClick={() => {
              if (position === "support") {
                return;
              }
              onChange({ body, position: "support", visible });
            }}
            className={
              "select-none transition px-2 py-1 rounded-lg text-sm " +
              (position === "support"
                ? "cursor-default bg-blue-200 rounded-lg"
                : "hover:bg-blue-50 active:bg-blue-100")
            }
          >
            Supporter
          </span>
          <span
            role="button"
            onClick={() => {
              if (position === "oppose") {
                return;
              }
              onChange({ body, position: "oppose", visible });
            }}
            className={
              "select-none transition px-2 py-1 rounded-lg text-sm " +
              (position === "oppose"
                ? "cursor-default bg-red-200 rounded-lg"
                : "hover:bg-red-50 active:bg-red-100")
            }
          >
            Opponent
          </span>
        </div>
      </div>
    </div>
  );
}

export default EditableChatMessage;

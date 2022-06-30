import React, { useCallback } from "react";
import EditableChatMessage from "./EditableChatMessage";
import { TemplateConversationItem } from "./types";

function TemplateChatList({
  data,
  onChange = () => {},
}: {
  data: TemplateConversationItem[];
  onChange?: (value: TemplateConversationItem[]) => void;
}) {
  const onChangeItem = useCallback(
    (item: TemplateConversationItem, index: number) => {
      onChange(data.map((d, i) => (i === index ? item : d)));
    },
    [data, onChange]
  );

  return (
    <div className="flex flex-col p-2 h-full">
      {data.map((item, index) => {
        return (
          <div key={index} className="mb-1">
            <EditableChatMessage
              data={item}
              onChange={(value) => onChangeItem(value, index)}
              onDelete={() => onChange(data.filter((_, i) => i !== index))}
            />
          </div>
        );
      })}
      <div className="w-full flex justify-center">
        <span
          role="button"
          className="material-icons select-none text-2xl text-slate-600 hover:bg-slate-400 transition mt-4 w-12 h-12 bg-slate-300 rounded-full flex items-center justify-center mb-3"
          onClick={() =>
            onChange([
              ...data,
              { body: "", position: "support", visible: true },
            ])
          }
        >
          add
        </span>
      </div>
    </div>
  );
}

export default TemplateChatList;

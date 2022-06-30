import React from "react";
import EditableChatMessage from "./EditableChatMessage";

function EditableDataList({
  data,
}: {
  data: { [s: string]: string | number }[];
}) {
  return (
    <div className="flex flex-col">
      {data.map((item, index) => (
        <div key={index} className="flex border-b font-mono">
          <div className="py-2.5 px-4 text-sm border-r">{index}</div>
          <ul className="p-3 text-xs">
            {Object.entries(item).map(([key, value]) => {
              return (
                <li key={key}>
                  <b>{key}:</b>&nbsp;
                  <span
                    contentEditable="true"
                    className="leading-none bg-slate-200"
                  >
                    {value}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}

export default EditableDataList;

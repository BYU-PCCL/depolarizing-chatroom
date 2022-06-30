import React from "react";
import TemplateEditor from "./TemplateEditor";

function SubTemplateList({
  data,
  errors = {},
  onChange = () => {},
  onDeleteTemplate = () => {},
}: {
  data: { [key: string]: string };
  errors?: { [key: string]: string };
  onChange?: (name: string, value: string) => void;
  onDeleteTemplate?: (id: string) => void;
}) {
  return (
    <div className="flex flex-col">
      {Object.entries(data).map(([id, body], index) => (
        <div key={id} className="border-b">
          <div className="flex items-center justify-between border-b pr-2">
            <h2
              className="p-3 text-base font-mono font-black"
              // style={{ color: "#8b5cf6" }}
            >
              {id}
            </h2>
            <span
              role="button"
              onClick={() => onDeleteTemplate(id)}
              className="material-icons transition hover:bg-slate-200 active:bg-slate-300 select-none rounded-full text-slate-600 p-2"
            >
              delete_outline
            </span>
          </div>
          <div className="h-44 flex">
            <TemplateEditor
              value={body}
              templateNames={[]}
              onChange={(value) => value && onChange(id, value)}
              error={errors[id] ?? ""}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export default SubTemplateList;

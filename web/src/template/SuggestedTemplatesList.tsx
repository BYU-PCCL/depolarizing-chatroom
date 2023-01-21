import React from "react";

function SuggestedTemplatesList({
  data,
  onTemplateAddClick = () => {},
}: {
  data: string[];
  onTemplateAddClick?: (name: string) => void;
}) {
  return (
    <div className="flex flex-col">
      {data.map((name, index) => (
        <div key={index} className="flex items-center border-b pl-2">
          <span
            role="button"
            onClick={() => onTemplateAddClick(name)}
            className="material-icons transition hover:bg-slate-200 active:bg-slate-300 select-none rounded-full p-2"
          >
            add
          </span>
          <h2 className="p-3 text-base font-mono font-black">{name}</h2>
        </div>
      ))}
    </div>
  );
}

export default SuggestedTemplatesList;

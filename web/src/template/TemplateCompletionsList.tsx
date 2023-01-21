import React from "react";

function TemplateCompletionsList({ completions }: { completions: string[] }) {
  return (
    <div className="flex flex-col p-2 gap-2">
      {completions.map((completion, index) => (
        <div
          key={index}
          className="flex px-3 py-2 text-sm bg-green-200 rounded-xl"
        >
          {completion}
        </div>
      ))}
    </div>
  );
}

export default TemplateCompletionsList;

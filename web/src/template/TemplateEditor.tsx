import Editor, { Monaco } from "@monaco-editor/react";
import { useCallback, useEffect, useRef } from "react";
import { editor } from "monaco-editor";
// import { editor } from "monaco-editor";

function getVariableTypeAndModifier(
  token: string,
  templates: Map<string, number>
) {
  if (token === "data") {
    return [0, 0];
  }

  let templateToken: number | undefined;
  if ((templateToken = templates.get(token)) !== undefined) {
    return [2, templateToken + 1];
  }

  return [-1, -1];
}

function editorSetup(monaco: Monaco) {
  monaco.languages.setMonarchTokensProvider("prompt-engineering-jinja", {
    tokenizer: {
      root: [
        [
          /\{\{/,
          {
            token: "template.inline",
            next: "@template",
            nextEmbedded: "python",
          },
        ],
        [/\{#/, "template.comment", "@comment"],
      ],
      template: [
        [/([^}]|}(?!}))/g, "template.inline"],
        [
          /}}/,
          { token: "template.inline", next: "@pop", nextEmbedded: "@pop" },
        ],
      ],
      comment: [
        [/([^#]|#(?!}))/g, "template.comment"],
        [/#}/, "template.comment", "@pop"],
      ],
    },
  });

  monaco.languages.register({ id: "prompt-engineering-jinja" });

  // add some missing tokens
  monaco.editor.defineTheme("prompt-engineering-jinja-theme", {
    base: "vs",
    inherit: true,
    colors: {},
    rules: [
      { token: "template.inline", fontStyle: "bold" },
      {
        token: "template.comment",
        foreground: "#808080",
        fontStyle: "italic",
      },
      { token: "quotes", foreground: "#51abec", fontStyle: "bold" },
      { token: "unterminated-space", foreground: "EC5151" },

      { token: "dataName", foreground: "#72a91c" },
      { token: "template", fontStyle: "bold italic" },

      { token: "inputField.color1", foreground: "#f43f5e" },
      { token: "inputField.color2", foreground: "#d946ef" },
      { token: "inputField.color3", foreground: "#8b5cf6" },
      { token: "inputField.color4", foreground: "#3b82f6" },
      { token: "inputField.color5", foreground: "#0ea5e9" },
      { token: "inputField.color6", foreground: "#14b8a6" },
      { token: "inputField.color7", foreground: "#22c55e" },
      { token: "inputField.color8", foreground: "#eab308" },
      { token: "inputField.color9", foreground: "#f97316" },
      { token: "inputField.color10", foreground: "#ef4444" },

      { token: "template.color1", foreground: "#f43f5e" },
      { token: "template.color2", foreground: "#d946ef" },
      { token: "template.color3", foreground: "#8b5cf6" },
      { token: "template.color4", foreground: "#3b82f6" },
      { token: "template.color5", foreground: "#0ea5e9" },
      { token: "template.color6", foreground: "#14b8a6" },
      { token: "template.color7", foreground: "#22c55e" },
      { token: "template.color8", foreground: "#eab308" },
      { token: "template.color9", foreground: "#f97316" },
      { token: "template.color10", foreground: "#ef4444" },
    ],
  });
}

function TemplateEditor({
  value,
  templateNames,
  error = "",
  onChange = () => {},
}: {
  value: string;
  templateNames: string[];
  error?: string;
  onChange?: (value: string | undefined) => void;
}) {
  const monacoRef = useRef<Monaco | null>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  const registerSemanticTokensProvider = useCallback(() => {
    if (!monacoRef.current) {
      return;
    }

    const templates = new Map<string, number>(
      templateNames.map((name, index) => [name, index])
    );

    monacoRef.current.languages.registerDocumentSemanticTokensProvider(
      "prompt-engineering-jinja",
      {
        getLegend: function () {
          return {
            tokenTypes: ["dataName", "inputField", "template"],
            tokenModifiers: [
              "color1",
              "color2",
              "color3",
              "color4",
              "color5",
              "color6",
              "color7",
              "color8",
              "color9",
              "color10",
            ],
          };
        },
        provideDocumentSemanticTokens: function (model, lastResultId, token) {
          if (!monacoRef.current) {
            return;
          }
          const tokens = monacoRef.current.editor.tokenize(
            model.getValue(),
            "prompt-engineering-jinja"
          );
          const lines = model.getLinesContent();

          const data: number[] = [];

          let prevLine = 0;
          let prevChar = 0;

          for (let i = 0; i < tokens.length; i++) {
            const line = tokens[i];

            for (let j = 0; j < line.length - 1; j++) {
              const match = line[j];
              let type = match.type;

              if (type !== "identifier.python") {
                continue;
              }

              const nextMatch = line[j + 1];
              const token = lines[i].slice(match.offset, nextMatch.offset);

              const [variableType, modifierIndex] = getVariableTypeAndModifier(
                token,
                templates
              );

              if (
                variableType === undefined ||
                modifierIndex === undefined ||
                modifierIndex === -1
              ) {
                continue;
              }

              data.push(
                // translate line to deltaLine
                i - prevLine,
                // for the same line, translate start to deltaStart
                prevLine === i ? match.offset - prevChar : match.offset,
                nextMatch.offset - match.offset,
                variableType,
                (1 << modifierIndex) >>> 0
                // (1 << 0) >>> 0
              );

              prevLine = i;
              prevChar = match.offset;
            }
          }
          return {
            data: new Uint32Array(data),
          };
        },
        releaseDocumentSemanticTokens: function (resultId) {},
      }
    );
  }, [templateNames]);

  function handleEditorDidMount(
    editor: editor.IStandaloneCodeEditor,
    monaco: Monaco
  ) {
    monacoRef.current = monaco;
    editorRef.current = editor;
    editor.addCommand(
      monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
      function () {}
    );
    registerSemanticTokensProvider();
  }

  useEffect(() => {
    registerSemanticTokensProvider();
  }, [templateNames]);

  return (
    <div className="flex-grow flex flex-col relative">
      <Editor
        width="100%"
        defaultLanguage="prompt-engineering-jinja"
        theme="prompt-engineering-jinja-theme"
        options={{
          "semanticHighlighting.enabled": true,
          minimap: { enabled: false },
          lineDecorationsWidth: 0,
          automaticLayout: true,
          wordWrap: "on",
        }}
        value={value}
        onChange={(value) => onChange(value)}
        beforeMount={editorSetup}
        onMount={handleEditorDidMount}
      />
      <div
        className={
          "p-2 bottom-0 w-full absolute text-xs font-mono border-t flex-grow " +
          (error ? "bg-red-200" : "bg-slate-50")
        }
      >
        {error || "No errors."}
      </div>
    </div>
  );
}

export default TemplateEditor;

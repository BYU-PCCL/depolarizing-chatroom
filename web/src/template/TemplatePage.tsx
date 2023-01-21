import React, {
  ChangeEvent,
  FormEvent,
  useCallback,
  useEffect,
  useState,
} from "react";
import TemplateEditor from "./TemplateEditor";
import SubTemplateList from "./SubTemplateList";
import SuggestedTemplatesList from "./SuggestedTemplatesList";
import TemplateChatList from "./TemplateChatList";
import TemplateCompletionsList from "./TemplateCompletionsList";
import { TemplateConversationItem } from "./types";

const EXAMPLE_DATA = [
  {
    position: "support",
    body: "I want to get rid of all guns right now. The United Lorem of Ipsum States protects my Dolor to the Set of the Constitutional Ipsum.",
  },
  {
    position: "oppose",
    body: "We need guns or we will die tragic, tragic deaths.",
  },
  {
    position: "support",
    body: "Again, we need to totally get rid of guns.",
  },
];

const EXAMPLE_TEMPLATES = [
  {
    id: "turn",
    body:
      "{# Here we use another template, 'position_description'. #}\n" +
      "{{ position_description|title }}: {{ data.body }}",
  },
  {
    id: "position_description",
    body: '{{ {"oppose": "opponent", "support": "supporter"}[data.position] }}',
  },
];

const EXAMPLE_SUGGESTED_TEMPLATES = [
  "suggested_template_1",
  "suggested_template_2",
];

const EXAMPLE_EDITABLE_CHAT_DATA: {
  position: "support" | "oppose";
  body: string;
  visible: boolean;
}[] = [
  {
    position: "support",
    body: "I want to get rid of all guns right now. The United Lorem of Ipsum States protects my Dolor to the Set of the Constitutional Ipsum.",
    visible: true,
  },
  {
    position: "oppose",
    body: "We need guns or we will die tragic, tragic deaths.",
    visible: false,
  },
  {
    position: "support",
    body: "Again, we need to totally get rid of guns.",
    visible: true,
  },
];

const EXAMPLE_COMPLETIONS = [
  "I understand you're feeling very upset about gun control. But what can we do?",
  "I really appreciate you taking the time to chat about gun control. Criminalizing guns won't make us safer.",
  "I think your viewpoint is very well considered. But have you thought about the victims of mass shootings? Surely they would feel differently.",
  "I think your viewpoint is very well considered. But have you thought about the victims of mass shootings? Surely they would feel differently.",
  "I think your viewpoint is very well considered. But have you thought about the victims of mass shootings? Surely they would feel differently.",
  "I think your viewpoint is very well considered. But have you thought about the victims of mass shootings? Surely they would feel differently.",
  "I think your viewpoint is very well considered. But have you thought about the victims of mass shootings? Surely they would feel differently.",
];

const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000/";

async function getTemplate(username: string) {
  const response = await fetch(API_URL + "template/" + username);
  return await response.json();
}

async function getPreview(username: string) {
  const response = await fetch(API_URL + "template/preview/" + username);
  return (await response.json()).preview;
}

async function getCompletions(username: string) {
  const response = await fetch(API_URL + "template/completions/" + username);
  return (await response.json()).completions;
}

async function checkTemplate(
  username: string,
  template: string,
  value: string
) {
  const response = await fetch(API_URL + "template/parse/" + username, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ template, value }),
  });
  return await response.json();
}

async function updateConversation(
  username: string,
  conversation: TemplateConversationItem[]
) {
  const response = await fetch(API_URL + "template/" + username, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ data: conversation }),
  });
  return await response.json();
}

function TemplatePage() {
  const [rootTemplate, setRootTemplate] = useState("");
  const [rootError, setRootError] = useState("");
  const [templateErrors, setTemplateErrors] = useState({});
  const [templates, setTemplates] = useState({});
  const [templateNames, setTemplateNames] = useState([]);
  const [conversation, setConversation] = useState<TemplateConversationItem[]>(
    []
  );
  const [loadingCompletions, setLoadingCompletions] = useState(false);
  const [completions, setCompletions] = useState([]);
  const [preview, setPreview] = useState<string | undefined>(undefined);
  const [showingPreview, setShowingPreview] = useState(false);

  const [username, setUsername] = useState<string | undefined>(undefined);
  const [usernameInput, setUsernameInput] = useState("");

  const [suggestedTemplates, setSuggestedTemplates] = useState([]);

  useEffect(() => {
    // If templateUsername is in localStorage, use that.
    const templateUsername = localStorage.getItem("templateUsername");
    if (templateUsername) {
      setUsername(templateUsername);
      setUsernameInput(templateUsername);
    }
  }, []);

  // Get initial data from server
  useEffect(() => {
    if (!username) {
      return;
    }
    getTemplate(username).then((data) => {
      setRootTemplate(data.root);
      setTemplates(data.templates);
      setConversation(data.data);
    });
  }, [username]);

  // Initial preview fetch
  useEffect(() => {
    if (!username) {
      return;
    }

    if (showingPreview) {
      getPreview(username).then((data) => setPreview(data));
    }
  }, [username, showingPreview]);

  const onTemplateChange = useCallback(
    (template: string, value: string | undefined) => {
      if (value === undefined || username === undefined) {
        return;
      }
      checkTemplate(username, template, value).then((data) => {
        if (data.errors) {
          setRootError(data.errors.root ?? "");
          setTemplateErrors(data.errors ?? {});
          return;
        }
        if (showingPreview) {
          getPreview(username).then((data) => setPreview(data));
        }
        setRootError("");
        setTemplateErrors({});

        setTemplateNames(data.names);
      });
    },
    [username, showingPreview]
  );

  // A list of every string in templateNames but not in the keys of templates
  // This is really inefficient but we don't expect to have many template names
  const suggestedTemplatesNames = templateNames.filter(
    (name) => !Object.keys(templates).includes(name)
  );

  const handleSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      localStorage.setItem("templateUsername", usernameInput);
      setUsername(usernameInput);
      event.preventDefault();
    },
    [usernameInput]
  );

  const handleUsernameChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      setUsernameInput(event.target.value);
    },
    []
  );

  const handleChangeConversation = useCallback(
    (conversation: TemplateConversationItem[]) => {
      if (username === undefined) {
        return;
      }

      updateConversation(username, conversation);
      if (showingPreview) {
        getPreview(username).then((data) => setPreview(data));
      }
      setConversation(conversation);
    },
    [username, showingPreview]
  );

  const handleReloadCompletions = useCallback(() => {
    if (username === undefined) {
      return;
    }
    setLoadingCompletions(true);
    getCompletions(username)
      .then((data) => setCompletions(data))
      .then(() => setLoadingCompletions(false));
  }, [username]);

  return (
    <div className="h-full flex flex-row">
      <div className="w-1/4 border-r flex flex-col">
        <div className="flex flex-col h-1/2">
          <div className="p-3 border-b">
            <h1 className="text-lg font-bold mb-2">Editable conversation</h1>
            <p>
              <span>Click to edit. Available in template as </span>
              <code className="font-bold">data</code>.
            </p>
          </div>
          <div className="overflow-scroll bg-gradient-to-b from-white via-white to-slate-100 h-full">
            <TemplateChatList
              data={conversation}
              onChange={handleChangeConversation}
            />
          </div>
        </div>
        <div className="h-1/2 border-t flex flex-col">
          <div className="p-3 border-b flex justify-between items-center">
            <h1 className="text-lg font-bold">Completions</h1>
            <div
              role="button"
              className="select-none transition flex items-center gap-1.5 text-md bg-green-300 px-2 py-0.5 rounded-lg pr-3 hover:bg-green-400"
              onClick={handleReloadCompletions}
            >
              <span className="material-icons">refresh</span>
              <span>Generate</span>
            </div>
          </div>
          <div className="overflow-scroll">
            {loadingCompletions ? (
              <div className="text-center py-10">
                <svg
                  role="status"
                  className="inline w-12 h-12 text-transparent animate-spin fill-green-600"
                  viewBox="0 0 100 101"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z"
                    fill="currentColor"
                  />
                  <path
                    d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z"
                    fill="currentFill"
                  />
                </svg>
              </div>
            ) : completions.length ? (
              <TemplateCompletionsList completions={completions} />
            ) : (
              <div className="p-3">
                <p className="text-sm">Click "generate" to get completions.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="flex flex-col flex-1">
        <div className="p-3 text-2xl border-b flex gap-2.5 items-center">
          <span>Editing as </span>
          <form onSubmit={handleSubmit}>
            <input
              type="text"
              className="border-2 rounded-lg px-2 py-1 border-black"
              placeholder="username"
              value={usernameInput}
              onChange={handleUsernameChange}
            />
          </form>
        </div>
        <div className="h-full w-full relative">
          <div className="h-full w-full flex">
            <TemplateEditor
              value={rootTemplate}
              templateNames={templateNames}
              error={rootError}
              onChange={(value) => onTemplateChange("root", value)}
            />
          </div>
          {showingPreview && (
            <div className="whitespace-pre-wrap overflow-scroll h-full p-2 absolute top-0 w-full bg-white">
              {preview ?? "Loading preview..."}
            </div>
          )}
        </div>
        <div className="p-3 border-t flex gap-1 justify-between items-center">
          <div className="flex gap-1">
            <div
              role="button"
              className={
                "transition select-none rounded-md py-2 px-3 " +
                (showingPreview ? "hover:bg-slate-200" : "bg-slate-300")
              }
              onClick={() => setShowingPreview(false)}
            >
              Edit
            </div>
            <div
              role="button"
              className={
                "transition select-none rounded-md py-2 px-3 " +
                (!showingPreview ? "hover:bg-slate-200" : "bg-slate-300")
              }
              onClick={() => setShowingPreview(true)}
            >
              Preview
            </div>
          </div>
        </div>
      </div>

      <div className="w-96 border-l">
        <div className="p-3 border-b">
          <h1 className="text-lg font-bold">Templates</h1>
        </div>
        <SubTemplateList
          data={templates}
          onChange={onTemplateChange}
          errors={templateErrors}
        />
        <SuggestedTemplatesList data={suggestedTemplatesNames} />
      </div>
    </div>
  );
}

export default TemplatePage;

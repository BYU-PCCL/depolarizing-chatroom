import React, { useCallback, useEffect, useRef, useState } from "react";
import PageWidth from "../common/PageWidth";
import { useChatroom, useUser } from "../api/hooks";
import TutorialRephrasingsModal from "./TutorialRephrasingsModal";
import ChatMessageList from "../common/ChatMessageList";
import { Link } from "react-router-dom";

interface TutorialMessage {
  type: string;
  body?: string;
  visible?: boolean;
  delay?: number;
}

// TODO: This should _definitely_ be moved to a separate file.
interface Message {
  body: string;
  time?: number;
  tutorial?: boolean;
  isSender: boolean;
}

const TUTORIAL_MESSAGES: TutorialMessage[] = [
  {
    type: "message",
    body: "Welcome to our chatroom! Part of the goal in these discussions is to find out if a chatroom tool can make suggestions to help these kinds of discussions be more productive.",
    delay: 4000,
  },
  {
    type: "message",
    body: "In your chat, you will occasionally see some suggestions about the message you want to send to your partner.",
    delay: 2000,
  },
  {
    type: "message",
    body: "This tutorial will help you understand the way that tool works before you actually chat with a partner. After you finish the tutorial, you will be matched with a person to talk to.",
    delay: 4000,
  },
  {
    type: "message",
    body: "Right now, this is just practice—you are not talking to another person yet.",
    delay: 3000,
  },
  {
    type: "message",
    body: "Part of our goal in these discussions is to find out if an artificial intelligence algorithm can make suggestions to help these kinds of discussions be more productive.",
    delay: 4000,
  },
  {
    type: "message",
    body: "Let's practice. I'll send you some messages:",
    delay: 3000,
  },
  {
    type: "ex-message",
    body: "I'm not actually your chat partner (or a person at all), but if I were, I would tell you what I think about this topic.",
    delay: 3000,
  },
  {
    type: "ex-message",
    body: "I'm interested to see how this conversation goes!",
    delay: 3000,
  },
  {
    type: "ex-message",
    body: "The traffic around my house has sure gotten worse in the last few months!",
    delay: 3000,
  },
  {
    type: "message",
    body: "Your turn! Type a response below and click the 'send' button.",
  },
  {
    type: "enable-response",
  },
  {
    type: "wait",
  },
  {
    type: "message",
    body: "You can see your message below, along with several alternatives.",
    delay: 2000,
  },
  {
    type: "message",
    body: "These might be better or worse than what you wanted to say.",
    delay: 2000,
  },
  {
    type: "message",
    body: "You can send your original message...",
  },
  {
    type: "highlight-original",
    visible: true,
    delay: 5000,
  },
  {
    type: "highlight-original",
    visible: false,
  },
  {
    type: "message",
    body: "...one of the suggested rephrasings...",
  },
  {
    type: "highlight-rephrasings",
    visible: true,
    delay: 4000,
  },
  {
    type: "message",
    body: "...or send a message that combines parts of each.",
  },
  {
    type: "highlight-original",
    visible: true,
  },
  {
    type: "highlight-rephrasings",
    visible: true,
    delay: 3000,
  },
  {
    type: "highlight-original",
    visible: false,
  },
  {
    type: "highlight-rephrasings",
    visible: false,
  },
  {
    type: "message",
    body: "Go ahead and pick a response.",
  },
  {
    type: "enable-rephrasings-response",
  },
  {
    type: "wait",
  },
  {
    type: "message",
    body: "Now that you've practiced, click on the button below to be paired with a chat partner. Please make sure to stay online as we find someone who disagrees with you on gun control.",
    delay: 2000,
  },
  {
    type: "message",
    body: "This will likely take a few minutes. You will be paid for your waiting time.",
    delay: 2000,
  },
  {
    type: "show-pair-button",
  },
];

const EXAMPLE_REPRHASINGS = [
  "Here is an alternative to what you said.",
  "Or, a second alternative.",
  "You could say this too, if you like.",
];

function TutorialPage() {
  const [composingMessage, setComposingMessage] = useState("");
  const [showingRephrasingsModal, setShowingRephrasingsModal] = useState(false);
  const [tutorialMessages, setTutorialMessages] = useState<Message[]>([]);
  const [popupMessages, setPopupMessages] = useState<Message[]>([]);
  const [enableResponse, setEnableResponse] = useState(false);
  const [enableRephrasingsResponse, setEnableRephrasingsResponse] =
    useState(false);
  const [tutorialMessageIndex, setTutorialMessageIndex] = useState(0);
  const [exampleResponse, setExampleResponse] = useState("");
  const [highlightingOriginal, setHighlightingOriginal] = useState(false);
  const [highlightingRephrasings, setHighlightingRephrasings] = useState(false);
  const [showingPairButton, setShowingPairButton] = useState(false);
  const chatMessagesElement = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const message = TUTORIAL_MESSAGES[tutorialMessageIndex];
    let isExampleMessage: boolean;

    if (
      message.type === "message" ||
      (isExampleMessage = message.type === "ex-message")
    ) {
      (showingRephrasingsModal ? setPopupMessages : setTutorialMessages)(
        (messages) => [
          ...messages,
          {
            body: message.body ?? "",
            isSender: false,
            tutorial: !isExampleMessage,
          },
        ]
      );
    } else if (message.type === "enable-response") {
      setEnableResponse(true);
    } else if (message.type === "wait") {
      return;
    } else if (message.type === "highlight-original") {
      if (message.visible === undefined) {
        return;
      }
      setHighlightingOriginal(message.visible);
    } else if (message.type === "highlight-rephrasings") {
      if (message.visible === undefined) {
        return;
      }
      setHighlightingRephrasings(message.visible);
    } else if (message.type === "show-pair-button") {
      setShowingPairButton(true);
    } else if (message.type === "enable-rephrasings-response") {
      setEnableRephrasingsResponse(true);
    }

    if (tutorialMessageIndex >= TUTORIAL_MESSAGES.length - 1) {
      return;
    }

    const timer = setTimeout(() => {
      setTutorialMessageIndex((index) => index + 1);
    }, message.delay ?? 0);

    return () => clearTimeout(timer);
  }, [showingRephrasingsModal, tutorialMessageIndex]);

  const sendTutorialMessage = useCallback(() => {
    setExampleResponse(composingMessage);
    setShowingRephrasingsModal(true);
    setEnableResponse(false);
    setComposingMessage("");
    const timer = setTimeout(() => {
      setTutorialMessageIndex((index) => index + 1);
    }, 400);
    return () => clearTimeout(timer);
  }, [composingMessage]);

  const sendRephrasing = useCallback((message: string) => {
    setShowingRephrasingsModal(false);
    setTutorialMessages((messages) => [
      ...messages,
      {
        body: message,
        isSender: true,
        tutorial: false,
        time: Date.now(),
      },
    ]);
    const timer = setTimeout(
      () => setTutorialMessageIndex((index) => index + 1),
      800
    );
    return () => clearTimeout(timer);
  }, []);

  const handleInputKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === "Enter") {
        event.preventDefault();
        sendTutorialMessage();
      }
    },
    [sendTutorialMessage]
  );

  useEffect(() => {
    if (chatMessagesElement.current) {
      chatMessagesElement.current.scrollTo({
        top: chatMessagesElement.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [tutorialMessages, showingPairButton]);

  return (
    <PageWidth>
      <span className="bg-green-600 text-white px-2 py-1 rounded-lg mb-3 text-2xl">
        Tutorial
      </span>
      <h1 className="text-4xl mb-10">Learn how to use our chatroom</h1>
      <div className="flex p-8 border border-green-600 rounded-xl flex-1 flex-col w-full bg-white bg-[#f8fefc]">
        <div
          ref={chatMessagesElement}
          className="flex-1 basis-0 overflow-scroll py-8 -my-8 px-7 -mx-7 mb-0"
        >
          <ChatMessageList messages={tutorialMessages} showTimes={false} />
          {showingPairButton && (
            <div className="mt-6">
              <Link
                className="transition rounded-lg px-4 py-3 text-lg bg-blue-600 hover:bg-blue-500 active:bg-blue-400 text-white"
                to="/waiting"
              >
                Find a chat
              </Link>
            </div>
          )}
        </div>
        <div className="border-t border-green-200 pt-5 w-full flex gap-4">
          <input
            className="border border-gray-300 rounded-md flex-1 px-3"
            value={composingMessage}
            onChange={(event) => setComposingMessage(event.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder={
              enableResponse ? "Type a message" : "Tutorial in progress..."
            }
            disabled={!enableResponse}
          ></input>
          <button
            className="rounded-full bg-blue-600 px-3.5 text-center drop-shadow-md hover:bg-blue-500 active:bg-blue-400 transition disabled:hover:bg-blue-300 disabled:bg-blue-300 disabled:drop-shadow-none"
            disabled={!enableResponse}
            onClick={sendTutorialMessage}
          >
            <span className="material-icons select-none p-2 text-white text-2xl">
              send
            </span>
          </button>
        </div>
      </div>
      <TutorialRephrasingsModal
        isOpen={showingRephrasingsModal}
        original={exampleResponse}
        enabled={enableRephrasingsResponse}
        rephrasings={EXAMPLE_REPRHASINGS}
        onSendOriginal={sendRephrasing}
        tutorialMessages={popupMessages}
        highlightingOriginal={highlightingOriginal}
        highlightingRephrasings={highlightingRephrasings}
        onSendRephrasing={(_, body) => sendRephrasing(body)}
      />
    </PageWidth>
  );
}

export default TutorialPage;

import React, { useCallback, useEffect, useRef, useState } from "react";
import PageWidth from "../common/PageWidth";
import TutorialRephrasingsModal from "./TutorialRephrasingsModal";
import ChatMessageList from "../common/ChatMessageList";
import { Link } from "react-router-dom";
import TypingIndicatorBubble from "../common/TypingIndicatorBubble";
import "../common/button.css";
import { useLiveWaitingRoom } from "./hooks";
import { ChatMessageState } from "../common/ChatMessage";

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
  state: ChatMessageState;
}

const TUTORIAL_MESSAGES: TutorialMessage[] = [
  {
    type: "message",
    body: "Welcome to our chatroom! Part of the goal in these discussions is to find out if a chatroom tool can help make conversations more productive.",
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
    body: "Let's practice. I'll send you some messages:",
    delay: 3000,
  },
  {
    type: "ex-message",
    body: "I'm not actually your chat partner (or a person at all), but if I were, I would tell you what I think. For example, I could say:",
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
    body: "You can see your message, along with several alternatives.",
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
    delay: 3000,
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
    delay: 3000,
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
    delay: 2000,
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
    body: "Now that you've practiced, click 'proceed' below to get started on your chat with your partner. The next thing we will ask you to do is explain your position on gun regulation and then your chat with your partner will begin.",
    delay: 2000,
  },
  {
    type: "show-pair-button",
  },
];

const EXAMPLE_REPRHASINGS = [
  "You could say this.",
  "Or you could say this.",
  "Here's a third alternative.",
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
  const [showingTypingBubble, setShowingTypingBubble] = useState(false);
  // This is such a terrible way to keep going about things. I apologize to you,
  // reader, for what this code has become .
  const [typingBubbleMessageType, setTypingBubbleMessageType] = useState<
    "tutorial" | "example"
  >("example");

  const chatMessagesElement = useRef<HTMLDivElement>(null);

  // This may seem a little overkill, but we need to let our partner know we're
  // still online while they're waiting for us to finish
  useLiveWaitingRoom("tutorial");

  useEffect(() => {
    const message = TUTORIAL_MESSAGES[tutorialMessageIndex];
    let isExampleMessage: boolean;

    setShowingTypingBubble(false);

    if (
      message.type === "message" ||
      (isExampleMessage = message.type === "ex-message")
    ) {
      (showingRephrasingsModal ? setPopupMessages : setTutorialMessages)(
        (messages) => [
          ...messages,
          {
            body: message.body ?? "",
            state: isExampleMessage ? "received" : "tutorial",
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

    let typingBubbleTimeout: NodeJS.Timeout | undefined;
    if (tutorialMessageIndex < TUTORIAL_MESSAGES.length - 2) {
      const nextMessage = TUTORIAL_MESSAGES[tutorialMessageIndex + 1];
      typingBubbleTimeout = setTimeout(() => {
        if (nextMessage.type === "message") {
          setTypingBubbleMessageType("tutorial");
        } else if (nextMessage.type === "ex-message") {
          setTypingBubbleMessageType("example");
        }
        setShowingTypingBubble(true);
      }, 500);
    }

    if (tutorialMessageIndex >= TUTORIAL_MESSAGES.length - 1) {
      return () => typingBubbleTimeout && clearTimeout(typingBubbleTimeout);
    }

    const timer = setTimeout(() => {
      setTutorialMessageIndex((index) => index + 1);
    }, message.delay ?? 0);

    return () => {
      clearTimeout(timer);
      typingBubbleTimeout && clearTimeout(typingBubbleTimeout);
    };
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
        state: "sender",
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
      <h1 className="text-4xl mb-6 sm:mb-10">Learn how to use our chatroom</h1>
      <div className="flex -mx-4 -mb-4 sm:mx-0 sm:mb-0 p-3 sm:p-8 flex-col h-full border-t sm:border border-green-600 sm:rounded-2xl bg-[#f8fefc] w-[calc(100%_+_2rem)] sm:w-full">
        <div className="flex sm:rounded-2xl flex-1 flex-col w-full h-full relative">
          <div
            ref={chatMessagesElement}
            className="flex-1 basis-0 overflow-scroll px-4 -mx-4 -my-3 pb-9 pt-3 mb-0 sm:py-9 sm:-my-8 sm:px-7 sm:-mx-7 sm:mb-0"
          >
            <ChatMessageList messages={tutorialMessages} showTimes={false} />
            {showingPairButton && (
              <div className="mb-4 sm:-mt-3 sm:mb-0 flex justify-center">
                <Link
                  className="transition rounded-lg px-4 py-2 text-lg bg-blue-600 hover:bg-blue-500 active:bg-blue-400 flex gap-2 text-white hero-button"
                  to="/view"
                >
                  <p>Proceed</p>
                  <span className="material-icons text-xl -mr-1 hero-button-arrow">
                    arrow_forward
                  </span>
                </Link>
              </div>
            )}
          </div>
          <div className="absolute bottom-2.5">
            <TypingIndicatorBubble
              fill={
                typingBubbleMessageType === "tutorial"
                  ? "green-600"
                  : "gray-500"
              }
              background={
                typingBubbleMessageType === "tutorial"
                  ? "green-200"
                  : "gray-200"
              }
              visible={showingTypingBubble && !showingRephrasingsModal}
            />
          </div>
        </div>
        <div className="border-t border-green-200 pt-3 sm:pt-6 w-full flex gap-4">
          <input
            className="border border-gray-300 rounded-md flex-1 px-3"
            value={composingMessage}
            onChange={(event) => setComposingMessage(event.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder={
              enableResponse ? "Type a message" : "Tutorial in progress..."
            }
            disabled={!enableResponse}
            size={1}
          ></input>
          <button
            className="rounded-full bg-blue-600 px-3.5 text-center hover:bg-blue-500 active:bg-blue-400 transition disabled:hover:bg-blue-300 disabled:bg-blue-300"
            disabled={!enableResponse}
            onClick={sendTutorialMessage}
          >
            <span className="material-icons select-none p-1.5 text-white text-2xl">
              send
            </span>
          </button>
        </div>
      </div>
      <TutorialRephrasingsModal
        isOpen={showingRephrasingsModal}
        showingTypingBubble={showingTypingBubble && showingRephrasingsModal}
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

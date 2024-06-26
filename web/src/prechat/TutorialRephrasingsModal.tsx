import Modal from "react-modal";
import { useCallback, useEffect, useRef } from "react";
import ComposeMessage from "../chatroom/ComposeMessage";
import ChatMessageList from "../common/ChatMessageList";
import TypingIndicatorBubble from "../common/TypingIndicatorBubble";

const customModalStyles = {
  content: {
    top: "50%",
    left: "50%",
    right: "auto",
    bottom: "auto",
    marginRight: "-50%",
    transform: "translate(-50%, -50%)",
    width: "min(800px, 90vw)",
    borderRadius: "15px",
  },
};

function TutorialRephrasingsModal({
  isOpen,
  showingTypingBubble,
  original,
  rephrasings,
  tutorialMessages,
  enabled = false,
  highlightingOriginal = false,
  highlightingRephrasings = false,
  onSendOriginal = () => {},
  onSendRephrasing = () => {},
}: {
  isOpen: boolean;
  showingTypingBubble: boolean;
  original: string;
  rephrasings: string[];
  tutorialMessages: any[];
  enabled?: boolean;
  highlightingOriginal?: boolean;
  highlightingRephrasings?: boolean;
  onSendOriginal?: (body: string) => void;
  onSendRephrasing?: (index: number, body: string) => void;
}) {
  const rephrasingsContainerRef = useRef<HTMLDivElement>(null);
  const loadingPanelRef = useRef<HTMLDivElement>(null);
  const rephrasingsPanelRef = useRef<HTMLDivElement>(null);
  const rephrasingsVisible = rephrasings.length > 0;
  const chatMessagesElement = useRef<HTMLDivElement>(null);

  const updateContainerHeight = useCallback(() => {
    if (
      !rephrasingsContainerRef.current ||
      !loadingPanelRef.current ||
      !rephrasingsPanelRef.current
    ) {
      return;
    }

    const scrollHeightTarget = rephrasingsVisible
      ? rephrasingsPanelRef.current
      : loadingPanelRef.current;

    rephrasingsContainerRef.current.style.height = `${scrollHeightTarget.scrollHeight}px`;
  }, [rephrasingsVisible]);

  useEffect(() => {
    updateContainerHeight();
  }, [rephrasings, isOpen, updateContainerHeight]);

  useEffect(() => {
    if (chatMessagesElement.current) {
      chatMessagesElement.current.scrollTo({
        top: chatMessagesElement.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [tutorialMessages]);

  return (
    <Modal
      isOpen={isOpen}
      onAfterOpen={updateContainerHeight}
      style={customModalStyles}
      contentLabel="Rephrasings Modal"
    >
      <div className="flex flex-col items-stretch sm:flex-row -m-1.5 sm:m-0">
        <div className="relative sm:ml-2 sm:mr-3 sm:mt-3 sm:-mb-5 sm:p-0 h-40 sm:h-[initial]">
          <div
            ref={chatMessagesElement}
            className="flex-1 basis-0 overflow-scroll px-3 pt-3 sm:-ml-3 sm:mr-2 sm:-mt-4 h-full pb-0 sm:-mb-6 sm:w-72 lg:w-96 border border-green-600 rounded-lg [overflow-anchor:none]"
          >
            <ChatMessageList messages={tutorialMessages} showTimes={false} />
          </div>

          <div className="absolute bottom-6 ml-3 -mb-3 sm:m-0">
            <TypingIndicatorBubble
              fill="green-800"
              background="green-200"
              visible={showingTypingBubble}
            />
          </div>
        </div>
        <div className="flex grow">
          <div
            className={
              "w-full py-3 px-2" + (!enabled ? " pointer-events-none" : "")
            }
          >
            <div className="gap-3 center pb-4 -mt-2 border-b items-center hidden sm:flex">
              <span className="material-icons text-2xl">edit</span>
              <p>Click any message to edit before sending.</p>
            </div>
            <h1
              className={
                "text-xl sm:text-2xl mt-0 my-3 sm:my-6 transition" +
                (highlightingOriginal ? " text-green-600" : "")
              }
            >
              Your message
            </h1>
            <ComposeMessage
              body={original}
              onSend={onSendOriginal}
              colors={
                highlightingOriginal
                  ? ["green-400", "green-500", "green-600"]
                  : ["black", "gray-500", "black"]
              }
            />
            <h1
              className={
                "my-3 sm:my-6 text-xl sm:text-2xl transition" +
                (highlightingRephrasings ? " text-green-600" : "")
              }
            >
              Some alternatives
            </h1>
            <div
              className="relative transition-height"
              ref={rephrasingsContainerRef}
            >
              <div
                className={
                  "w-full flex items-center justify-center h-32 transition-opacity" +
                  (rephrasingsVisible ? " opacity-0" : "")
                }
                ref={loadingPanelRef}
              >
                <svg
                  role="status"
                  className="inline w-12 h-12 text-transparent animate-spin fill-blue-600"
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
              <div
                className={
                  "w-full flex flex-col gap-3 absolute top-0 transition-opacity" +
                  (rephrasingsVisible ? "" : " opacity-0 pointer-events-none")
                }
                ref={rephrasingsPanelRef}
              >
                {rephrasings.map((rephrasing, i) => (
                  <ComposeMessage
                    key={i}
                    body={rephrasing}
                    onChange={updateContainerHeight}
                    onSend={(body) => onSendRephrasing(i, body)}
                    colors={["400", "200", "600"].map(
                      (value) =>
                        (highlightingRephrasings ? "green" : "blue") +
                        "-" +
                        value
                    )}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </Modal>
  );
}

export default TutorialRephrasingsModal;

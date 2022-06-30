import ComposeMessage from "./ComposeMessage";
import Modal from "react-modal";
import { useCallback, useEffect, useRef, useState } from "react";

const customModalStyles = {
  content: {
    top: "50%",
    left: "50%",
    right: "auto",
    bottom: "auto",
    marginRight: "-50%",
    transform: "translate(-50%, -50%)",
    width: "500px",
    borderRadius: "10px",
  },
};

function LeaveModal({
  isOpen,
  onConfirm = () => {},
  onCancel = () => {},
}: {
  isOpen: boolean;
  onConfirm?: (reason: string) => void;
  onCancel?: () => void;
}) {
  const [reason, setReason] = useState("");

  return (
    <Modal
      isOpen={isOpen}
      style={customModalStyles}
      contentLabel="Leave Chatroom Modal"
    >
      <div className="w-full py-3 px-2 flex flex-col gap-5">
        <h1 className="text-2xl">Leave the chat</h1>
        <p>
          We're sorry you're having trouble with the conversation. So that we
          can review these conversations and determine people's payments, please
          tell us why you need to leave the chat room early.
        </p>
        <textarea
          className="w-full border-2 rounded-lg h-36 p-3"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        ></textarea>
        <p>
          Which you click 'leave', you will be taken to the final survey and
          payment page. If you would like to close this window and go back to
          the chat, please click 'cancel'.
        </p>
        <div className="flex gap-2 w-full justify-end">
          <button
            className="transition bg-gray-300 hover:bg-gray-400 active:bg-gray-500 text-black font-bold py-2 px-4 rounded"
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            className="transition bg-gray-300 hover:bg-gray-400 active:bg-gray-500 text-black font-bold py-2 px-4 rounded"
            onClick={() => onConfirm(reason)}
          >
            Leave
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default LeaveModal;

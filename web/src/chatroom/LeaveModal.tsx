import Modal from "react-modal";
import { useState } from "react";

const customModalStyles = {
  content: {
    top: "50%",
    left: "50%",
    right: "auto",
    bottom: "auto",
    marginRight: "-50%",
    transform: "translate(-50%, -50%)",
    width: "min(700px, 90vw)",
    borderRadius: "10px",
    padding: "0",
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
      <div className="w-full p-5 sm:p-8 flex flex-col gap-5">
        <h1 className="text-2xl">Leave the chat early</h1>
        <b className="text-sm sm:text-base bg-yellow-200 px-5 -mx-5 sm:px-4 sm:-mx-4 py-3 sm:rounded-xl">
          The chatroom will normally notify you when you've completed the
          conversation.
        </b>
        <p className="text-sm sm:text-base">
          So that we can review these conversations and determine people's
          payments, please tell us why you need to leave the chat room early.
        </p>
        <textarea
          className="w-full border-2 rounded-lg h-36 p-3"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        ></textarea>
        <p className="text-sm sm:text-base">
          When you click 'leave', you will be taken to the final survey and
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
            className="transition bg-gray-300 hover:bg-gray-400 active:bg-gray-500 disabled:bg-gray-200 disabled:text-gray-500 text-black font-bold py-2 px-4 rounded"
            onClick={() => onConfirm(reason)}
            disabled={!reason}
          >
            Leave
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default LeaveModal;

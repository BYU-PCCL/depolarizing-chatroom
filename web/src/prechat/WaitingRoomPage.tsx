import React from "react";
import PageWidth from "../common/PageWidth";
import "../common/ellipsis.css";
import ErrorPage from "../common/ErrorPage";
import LoadingPage from "../common/LoadingPage";
import { useLiveWaitingRoom } from "./hooks";

function WaitingRoomPage() {
  const waitingRoom = useLiveWaitingRoom();

  if (waitingRoom.status === "loading") {
    return <LoadingPage />;
  }

  if (waitingRoom.status === "error") {
    // @ts-ignore
    return <ErrorPage error={waitingRoom.error.toString()} />;
  }

  let title;
  let icon;
  switch (waitingRoom.partnerStatus) {
    case "waiting":
      title = (
        <>
          Finding a chat partner<span>.</span>
          <span>.</span>
          <span>.</span>
        </>
      );
      icon = "sms";
      break;
    case "matched":
      title = (
        <>
          Waiting for your partner to finish<span>.</span>
          <span>.</span>
          <span>.</span>
        </>
      );
      icon = "3p";
      break;
    case "offline":
      title = <>Your partner left.</>;
      icon = "call_missed_outgoing";
      break;
  }

  return (
    <PageWidth>
      <div className="flex">
        <span
          className={
            "material-icons mb-6 sm:mb-8 text-6xl " +
            (waitingRoom.partnerStatus !== "offline"
              ? "text-blue-600"
              : "text-green-600")
          }
        >
          {icon}
        </span>
      </div>
      <h1 className="text-3xl mb-4 ellipsis">{title}</h1>
      <p>
        {waitingRoom.partnerStatus !== "offline" ? (
          <>
            Please don't close or refresh this page. You'll be redirected
            automatically.
          </>
        ) : (
          <>
            Click <b>finish</b> to continue to the last survey and receive your
            payment.
          </>
        )}
      </p>
      {waitingRoom.partnerStatus === "offline" && (
        <a
          className="transition rounded-lg px-4 py-2 text-lg bg-green-600 hover:bg-green-500 active:bg-green-400 text-white mt-8 span flex gap-2"
          href={waitingRoom.user?.no_chat_url as string}
        >
          <p>Finish</p>
          <span className="material-icons text-xl translate-y-[1px] -mr-1">
            arrow_forward
          </span>
        </a>
      )}
    </PageWidth>
  );
}

export default WaitingRoomPage;

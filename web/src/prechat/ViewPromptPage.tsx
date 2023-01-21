import PageWidth from "../common/PageWidth";
import { useNavigate } from "react-router-dom";
import React, { useCallback, useEffect, useState } from "react";
import { useUser } from "../api/hooks";
import { getEndpointUrl, getRequestWithBodyHeaders } from "../api/apiUtils";
import { useMutation } from "react-query";
import LoadingPage from "../common/LoadingPage";
import ErrorPage from "../common/ErrorPage";
import "../common/button.css";
import { useLiveWaitingRoom } from "./hooks";

function ViewPromptPage() {
  const [viewText, setViewText] = useState("");
  const [position, setPosition] = useState("");
  const user = useUser();
  const navigate = useNavigate();

  // This may seem a little overkill, but we need to let our partner know we're
  // still online while they're waiting for us to finish
  useLiveWaitingRoom("view");

  useEffect(() => {
    if (user.isLoading || user.isError) {
      return;
    }

    const position = user?.data?.position;

    if (position === undefined || typeof position !== "string") {
      return;
    }

    setPosition(
      position === "oppose" ? "about the same or less strict" : "more strict"
    );
  }, [user]);

  const mutation = useMutation(async () => {
    if (!viewText) {
      return;
    }

    const fetchResponse = await fetch(getEndpointUrl("initial-view"), {
      method: "POST",
      headers: getRequestWithBodyHeaders(),
      body: JSON.stringify({ view: viewText }),
    });

    if (!fetchResponse.ok) {
      throw new Error(fetchResponse.statusText);
    }

    return fetchResponse.json();
  });

  const handleContinueClick = useCallback(async () => {
    if (user.data === undefined) {
      return;
    }

    await mutation.mutate();
    const treatment = user?.data?.treatment;

    if (treatment === undefined || typeof treatment !== "number") {
      return;
    }

    // Literally wait a second to fight off a race condition because I am out of
    // good (easy) ideas. Not a problem if the user tries to click the
    setTimeout(() => {
      navigate("/waiting");
    }, 1000);
  }, [mutation.mutate, user.data]);

  if (user.isLoading) {
    return <LoadingPage />;
  }

  if (user.isError) {
    return <ErrorPage error={user.error.message} />;
  }

  return (
    <PageWidth>
      <span className="material-icons mb-4 sm:mb-8 text-6xl text-blue-600">
        forum
      </span>
      <h1 className="text-3xl mb-4">What is your position?</h1>
      <p>
        To get your conversation started with your chat partner, we will share
        with each of you a bit more about how the other person feels. To do that
        we'd like you to explain a bit more about your position on gun laws. A
        moment ago, you stated that you felt gun laws should be&nbsp;
        <b>{position}</b>. In the box below, please explain why you feel this
        way—we will share this message with your chat partner.
      </p>
      <textarea
        className="w-full mt-6 border-2 rounded-lg h-36 p-3"
        value={viewText}
        onChange={(event) => setViewText(event.target.value)}
      ></textarea>
      <button
        className={
          "transition rounded-lg px-4 py-2 text-lg bg-blue-600 hover:bg-blue-500 active:bg-blue-400 text-white mt-8 span flex gap-2 hero-button" +
          (viewText.length > 0 ? "" : " opacity-50 pointer-events-none")
        }
        onClick={handleContinueClick}
      >
        <p>Continue</p>
        <span className="material-icons text-xl translate-y-[1px] -mr-1 hero-button-arrow">
          arrow_forward
        </span>
      </button>
    </PageWidth>
  );
}

export default ViewPromptPage;

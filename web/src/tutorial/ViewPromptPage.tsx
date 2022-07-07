import PageWidth from "../common/PageWidth";
import { useNavigate } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import { useUser } from "../api/hooks";
import { getEndpointUrl, getRequestWithBodyHeaders } from "../api/apiUtils";
import { useMutation } from "react-query";

function ViewPromptPage() {
  const [viewText, setViewText] = useState("");
  const [position, setPosition] = useState("");
  const user = useUser();
  const navigate = useNavigate();

  useEffect(() => {
    if (user.isLoading || user.isError) {
      return;
    }

    const treatment = user?.data?.treatment;

    if (treatment === undefined || typeof treatment !== "number") {
      return;
    }

    setPosition(treatment > 3 ? "about the same or less strict" : "more strict");
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

  const handleContinueClick = useCallback(() => {
    if (user.data === undefined) {
      return;
    }

    mutation.mutate();
    const treatment = user?.data?.treatment;

    if (treatment === undefined || typeof treatment !== "number") {
      return;
    }

    if ((treatment - 1) % 3 === 0) {
      navigate("/tutorial");
    } else {
      navigate("/waiting");
    }
  }, [mutation.mutate, user.data]);

  if (user.isLoading) {
    return <div>Loading...</div>;
  }

  if (user.isError) {
    // @ts-ignore
    return <div>Error: {user.error.message}</div>;
  }

  return (
    <PageWidth>
      <span className="material-icons mb-8 text-6xl text-blue-600">forum</span>
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
          "transition rounded-lg px-4 py-2 text-lg bg-blue-600 hover:bg-blue-500 active:bg-blue-400 text-white mt-8 span flex gap-2" +
          (viewText.length > 0 ? "" : " opacity-50 pointer-events-none")
        }
        onClick={handleContinueClick}
      >
        <p>Continue</p>
        <span className="material-icons text-xl translate-y-[1px] -mr-1">
          arrow_forward
        </span>
      </button>
    </PageWidth>
  );
}

export default ViewPromptPage;

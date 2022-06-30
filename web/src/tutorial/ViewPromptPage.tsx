import PageWidth from "../common/PageWidth";
import { Link } from "react-router-dom";
import { useState } from "react";

function ViewPromptPage({ position = "more strict" }) {
  const [viewText, setViewText] = useState("");

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
      <Link
        className={
          "transition rounded-lg px-4 py-2 text-lg bg-blue-600 hover:bg-blue-500 active:bg-blue-400 text-white mt-8 span flex gap-2" +
          (viewText.length > 0 ? "" : " opacity-50 pointer-events-none")
        }
        to="/tutorial"
      >
        <p>Continue</p>
        <span className="material-icons text-xl translate-y-[1px] -mr-1">
          arrow_forward
        </span>
      </Link>
    </PageWidth>
  );
}

export default ViewPromptPage;

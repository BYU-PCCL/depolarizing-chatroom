import PageWidth from "../common/PageWidth";
import { Link } from "react-router-dom";
import "../common/button.css";

function IntroPage() {
  return (
    <PageWidth>
      <span className="material-icons mb-6 sm:mb-8 text-6xl text-blue-600">
        waving_hand
      </span>
      <h1 className="text-3xl mb-4">Introduction</h1>
      <p>
        Thank you for agreeing to chat with someone who disagrees with you on
        gun control. You will be asked have a substantial conversation with them
        on this topic, sharing your views and listening to theirs. Following the
        chat, you'll be redirected back to the survey to answer a few final
        questions and receive your payment code.
      </p>
      <Link
        className="transition rounded-lg px-4 py-2 text-lg bg-blue-600 hover:bg-blue-500 active:bg-blue-400 text-white mt-8 span flex gap-2 hero-button"
        to="/waiting"
      >
        <p>Continue</p>
        <span className="material-icons text-xl -mr-1 hero-button-arrow">
          arrow_forward
        </span>
      </Link>
    </PageWidth>
  );
}

export default IntroPage;

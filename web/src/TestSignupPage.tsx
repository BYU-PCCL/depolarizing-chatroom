import PageWidth from "./common/PageWidth";
import { useCallback, useState } from "react";
import { getEndpointUrl, setAuthCode } from "./api/apiUtils";
import { useMutation } from "react-query";
import { useNavigate } from "react-router-dom";

function TestSignupPage() {
  const [username, setUsername] = useState("");
  const [pairWith, setPairWith] = useState("");
  const [position, setPosition] = useState("support");
  const [applyTreatment, setApplyTreatment] = useState(false);
  const navigate = useNavigate();

  const mutation = useMutation(async () => {
    if (!username || !pairWith || !position) {
      return;
    }

    const fetchResponse = await fetch(getEndpointUrl("test-signup"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username, pairWith, position, applyTreatment }),
    });

    if (!fetchResponse.ok) {
      throw new Error(fetchResponse.statusText);
    }

    await setAuthCode(username);
    return fetchResponse.json();
  });

  const handleSubmit = useCallback(
    (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      mutation.mutate();
      navigate("/intro");
    },
    [mutation, navigate]
  );

  return (
    <PageWidth>
      <h1 className="mb-3 text-3xl">Test account signup</h1>
      <form onSubmit={handleSubmit} className="flex flex-col items-start">
        <input
          className="border border-gray-300 rounded-sm px-2 mb-3 w-96"
          type="text"
          placeholder="code (make something up but remember it)"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
        />
        <input
          className="border border-gray-300 rounded-sm px-2 mb-3 w-96"
          type="text"
          placeholder="username to pair with"
          value={pairWith}
          onChange={(event) => setPairWith(event.target.value)}
        />
        <span className="mb-3">
          You&nbsp;
          <select
            name="position"
            className="border border-gray-300 rounded-sm"
            value={position}
            onChange={(event) => setPosition(event.target.value)}
          >
            <option value="support">support</option>
            <option value="oppose">oppose</option>
          </select>
          &nbsp;increased gun control measures in America.
        </span>
        <span className="mb-3">
          <input
            type="checkbox"
            name="treated"
            checked={applyTreatment}
            onChange={(event) => setApplyTreatment(event.target.checked)}
          />
          <label htmlFor="treated">Apply treatment</label>
        </span>
        <input
          type="submit"
          className="border-2 border-blue-600 px-4 py-1 rounded-md text-blue-600"
          value="Sign up"
        />
      </form>
    </PageWidth>
  );
}

export default TestSignupPage;

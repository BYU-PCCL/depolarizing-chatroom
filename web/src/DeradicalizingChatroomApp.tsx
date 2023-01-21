import React, { useEffect, useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import TemplatePage from "./template/TemplatePage";
import ChatroomPage from "./chatroom/ChatroomPage";
import NoAuthPage from "./NoAuthPage";
import WaitingRoomPage from "./prechat/WaitingRoomPage";
import { useMutation, QueryClientProvider, QueryClient } from "react-query";
import TestSignupPage from "./TestSignupPage";
import { getAuthCode, getEndpointUrl, setAuthCode } from "./api/apiUtils";
import TutorialPage from "./prechat/TutorialPage";
import IntroPage from "./prechat/IntroPage";
import ViewPromptPage from "./prechat/ViewPromptPage";
import DashboardPage from "./DashboardPage";
import LoadingPage from "./common/LoadingPage";

const queryClient = new QueryClient();

function DeradicalizingChatroomApp() {
  return (
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/template" element={<TemplatePage />} />
        <Route
          path="/intro"
          element={
            <RequireAuth>
              <IntroPage />
            </RequireAuth>
          }
        />
        <Route
          path="/view"
          element={
            <RequireAuth>
              <ViewPromptPage />
            </RequireAuth>
          }
        />
        <Route
          path="/tutorial"
          element={
            <RequireAuth>
              <TutorialPage />
            </RequireAuth>
          }
        />
        <Route
          path="/chatroom"
          element={
            <RequireAuth>
              <ChatroomPage />
            </RequireAuth>
          }
        />
        <Route
          path="/waiting"
          element={
            <RequireAuth>
              <WaitingRoomPage />
            </RequireAuth>
          }
        />
        <Route path="/noauth" element={<NoAuthPage />} />
        <Route path="/test-signup" element={<TestSignupPage />} />
        <Route path="/" element={<LoginRoute />} />
        <Route path="/start" element={<StartRoute />} />
      </Routes>
    </QueryClientProvider>
  );
}

function LoginRoute() {
  // Get token from the URL
  const [token, setToken] = useState(
    new URLSearchParams(window.location.search).get("token")
  );

  // Use react query to mutate /login
  const mutation = useMutation(async () => {
    if (!token) {
      return;
    }

    const fetchResponse = await fetch(getEndpointUrl("login"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ token }),
    });

    if (!fetchResponse.ok) {
      throw new Error(fetchResponse.statusText);
    }

    await setAuthCode(token);
    return fetchResponse.json();
  });

  // If mutation is successful, navigate to chatroom
  useEffect(() => {
    if (!token) {
      return;
    }

    mutation.mutate();
  }, [mutation.mutate, token]);

  if (!token) {
    return <Navigate to="/noauth" replace />;
  }

  return mutation.isLoading ? (
    <div>Logging in...</div>
  ) : (
    // <Navigate to={mutation.isError ? "/noauth" : "/waiting"} replace />
    <>
      {mutation.isError && <Navigate to="/noauth" replace />}
      {/*{mutation.isSuccess && <Navigate to="/waiting" replace />}*/}
      {mutation.isSuccess && <Navigate to="/intro" replace />}
    </>
  );
}

function StartRoute() {
  // Get token from the URL
  const [respondentId, setRespondentId] = useState(
    new URLSearchParams(window.location.search).get("respondentID")
  );

  // Get treatment code from the URL
  const [position, setPosition] = useState(
    new URLSearchParams(window.location.search).get("position")
  );

  // Use react query to mutate /signup
  const mutation = useMutation(async () => {
    if (!respondentId || !position) {
      return;
    }

    const fetchResponse = await fetch(getEndpointUrl("signup"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ respondentId, position }),
    });

    if (!fetchResponse.ok) {
      throw new Error(fetchResponse.statusText);
    }

    await setAuthCode(respondentId);
    return fetchResponse.json();
  });

  // If mutation is successful, navigate to chatroom
  useEffect(() => {
    if (!respondentId || !position) {
      return;
    }

    mutation.mutate();
  }, [mutation.mutate, respondentId, position]);

  return mutation.isLoading ? (
    <LoadingPage />
  ) : (
    <>
      {mutation.isError && <Navigate to="/noauth" replace />}
      {mutation.isSuccess && <Navigate to="/intro" replace />}
    </>
  );
}

function RequireAuth({ children }: { children: JSX.Element }) {
  const authToken = getAuthCode();

  if (!authToken) {
    return <Navigate to="/noauth" replace />;
  }

  return children;
}

export default DeradicalizingChatroomApp;

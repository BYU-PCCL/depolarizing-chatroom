import React, { useEffect, useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import TemplatePage from "./template/TemplatePage";
import ChatroomPage from "./chatroom/ChatroomPage";
import NoAuthPage from "./NoAuthPage";
import WaitingRoomPage from "./tutorial/WaitingRoomPage";
import { useMutation, QueryClientProvider, QueryClient } from "react-query";
import { API_URL } from "./constants";
import TestSignupPage from "./TestSignupPage";
import { setAuthCode } from "./api/apiUtils";
import TutorialPage from "./tutorial/TutorialPage";
import IntroPage from "./tutorial/IntroPage";
import ViewPromptPage from "./tutorial/ViewPromptPage";

const queryClient = new QueryClient();

function DeradicalizingChatroomApp() {
  return (
    <QueryClientProvider client={queryClient}>
      <Routes>
        {/*<Route path="/" element={<Home />} />*/}
        <Route path="/intro" element={<IntroPage />} />
        <Route path="/view" element={<ViewPromptPage />} />
        <Route path="/template" element={<TemplatePage />} />
        <Route path="/tutorial" element={<TutorialPage />} />
        <Route
          path="/chatroom"
          // element={
          //   <RequireAuth>
          //     <TutorialPage />
          //   </RequireAuth>
          // }
          element={<ChatroomPage />}
        />
        <Route
          path="/waiting"
          // element={
          //   <RequireAuth>
          //     <TutorialPage />
          //   </RequireAuth>
          // }
          element={<WaitingRoomPage />}
        />
        <Route path="/noauth" element={<NoAuthPage />} />
        <Route path="/test-signup" element={<TestSignupPage />} />
        <Route path="/" element={<LoginRoute />} />
      </Routes>
    </QueryClientProvider>
  );
}

function LoginRoute() {
  // Get the token from the URL
  const [token, setToken] = useState(
    new URLSearchParams(window.location.search).get("token")
  );

  // Use react query to mutate /login
  const mutation = useMutation(async () => {
    if (!token) {
      return;
    }

    const fetchResponse = await fetch(`${API_URL}/login`, {
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
      {mutation.isSuccess && <Navigate to="/chatroom" replace />}
    </>
  );
}

function RequireAuth({ children }: { children: JSX.Element }) {
  const authToken = localStorage.getItem("token");

  if (!authToken) {
    return <Navigate to="/noauth" replace />;
  }

  return <div>{children}</div>;
}

export default DeradicalizingChatroomApp;

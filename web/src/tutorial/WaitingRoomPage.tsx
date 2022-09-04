import React, { useEffect, useState } from "react";
import PageWidth from "../common/PageWidth";
import { BASE_URL, getAuthCode, getEndpointUrl } from "../api/apiUtils";
import socketIOClient, { Socket } from "socket.io-client";
import { useNavigate } from "react-router-dom";
import "./waiting.css";

const WAITING_MESSAGES = [
  "You'll be redirected automatically in a moment.",
  "Waiting for a match...",
];

function WaitingRoomPage() {
  const [socket, setSocket] = useState<Socket | undefined>();
  const [messageIndex, setMessageIndex] = useState<number>(0);
  const navigate = useNavigate();

  useEffect(() => {
    if (socket) {
      return;
    }

    const localSocket: Socket = socketIOClient(
      getEndpointUrl("waiting-room").replace("/api", ""),
      {
        path: BASE_URL.endsWith("/api/")
          ? "/api/ws/socket.io"
          : "/ws/socket.io",
        auth: { token: getAuthCode() },
      }
    );
    localSocket.onAny((event: any, data: any) => console.debug(event, data));
    localSocket.on("redirect", ({ to }: { to: string }) => {
      if (to === "chatroom") {
        navigate("/chatroom");
      } else if (to === "view") {
        navigate("/view");
      }
    });
    setSocket(localSocket);
  }, [navigate, socket]);

  useEffect(() => {
    const interval = setInterval(() => {
      setMessageIndex(
        (messageIndex) => (messageIndex + 1) % WAITING_MESSAGES.length
      );
    }, 10000);

    return () => {
      clearInterval(interval);
    };
  }, []);

  return (
    <PageWidth>
      <div className="flex">
        <span className="material-icons mb-8 text-6xl text-blue-600">sms</span>
      </div>
      <h1 className="text-3xl mb-4 ellipsis">
        Finding a chat partner<span>.</span>
        <span>.</span>
        <span>.</span>
      </h1>
      <p>{WAITING_MESSAGES[messageIndex]}</p>
    </PageWidth>
  );
}

export default WaitingRoomPage;

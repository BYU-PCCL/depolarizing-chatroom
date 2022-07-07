import React, { useEffect, useState } from "react";
import PageWidth from "../common/PageWidth";
import { BASE_URL, getAuthCode, getEndpointUrl } from "../api/apiUtils";
import socketIOClient, { Socket } from "socket.io-client";
import { useNavigate } from "react-router-dom";

function WaitingRoomPage() {
  const [socket, setSocket] = useState<Socket | undefined>();
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

  return (
    <PageWidth>
      <div className="flex">
        <span className="material-icons mb-8 text-6xl text-blue-600">sms</span>
      </div>
      <h1 className="text-3xl mb-4">Waiting for a chat partner...</h1>
      <p>You'll be redirected automatically in a moment.</p>
    </PageWidth>
  );
}

export default WaitingRoomPage;

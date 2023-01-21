import { useCallback, useEffect, useRef, useState } from "react";
import socketIOClient, { Socket } from "socket.io-client";
import {
  ApiError,
  BASE_URL,
  getAuthCode,
  getEndpointUrl,
} from "../api/apiUtils";
import { useNavigate } from "react-router-dom";
import { useUser, useWaitingRoom } from "../api/hooks";

type WaitingRoomStatus = "loading" | "error" | "ready";
type PartnerStatus = "waiting" | "matched" | "offline";

const PARTNER_OFFLINE_TIMEOUT = 60_000;

export const useLiveWaitingRoom = (
  page: string = "waiting"
): {
  status: WaitingRoomStatus;
  error: ApiError | null;
  waitingRoom?: Record<string, unknown>;
  user?: Record<string, unknown>;
  socket?: Socket;
  partnerStatus?: PartnerStatus;
} => {
  const [socket, setSocket] = useState<Socket | undefined>();
  const [partnerStatus, setPartnerStatus] = useState<
    PartnerStatus | undefined
  >();
  const waitingRoom = useWaitingRoom();
  const user = useUser();
  const navigate = useNavigate();

  const partnerOfflineTimeoutRef = useRef<NodeJS.Timeout | undefined>();

  const handlePartnerStatusChange = useCallback((status: PartnerStatus) => {
    if (partnerOfflineTimeoutRef.current) {
      clearTimeout(partnerOfflineTimeoutRef.current);
      partnerOfflineTimeoutRef.current = undefined;
    }

    if (status === "offline") {
      partnerOfflineTimeoutRef.current = setTimeout(() => {
        setPartnerStatus("offline");
      }, PARTNER_OFFLINE_TIMEOUT);
    } else {
      setPartnerStatus(status);
    }
  }, []);

  // Socket setup
  useEffect(() => {
    if (waitingRoom.isLoading || waitingRoom.isError || socket) {
      if (socket && !socket.connected) {
        // And apparently only socket.io.connect works here
        socket.io.connect();
      }
      return;
    }
    const localSocket: Socket = socketIOClient(
      getEndpointUrl("waiting-room").replace("/api", ""),
      {
        path: BASE_URL.endsWith("/api/")
          ? "/api/ws/socket.io"
          : "/ws/socket.io",
        auth: { token: getAuthCode(), page },
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: Infinity,
      }
    );
    setSocket(localSocket);
    localSocket.on("disconnect", function () {
      setTimeout(() => {
        console.debug("Attempting to reconnect to waiting room socket...");
        localSocket.connect();
      }, 5000);
    });

    localSocket.on("partner_status", handlePartnerStatusChange);
    localSocket.on("redirect", ({ to, url }: { to?: string; url?: string }) => {
      if (url) {
        window.location.href = url;
        return;
      }

      if (to === "chatroom") {
        navigate("/chatroom");
      } else if (to === "view") {
        navigate("/view");
      } else if (to === "tutorial") {
        navigate("/tutorial");
      } else if (to === "waiting") {
        navigate("/waiting");
      }
    });
  }, [
    socket,
    navigate,
    page,
    waitingRoom.isLoading,
    waitingRoom.isError,
    handlePartnerStatusChange,
  ]);

  // Wait for partner status
  useEffect(() => {
    if (waitingRoom.isLoading || waitingRoom.isError) {
      return;
    }

    const partnerStatus = waitingRoom?.data?.partnerStatus as PartnerStatus;
    if (partnerStatus === "offline") {
      setPartnerStatus("matched");
      handlePartnerStatusChange(partnerStatus);
    } else {
      setPartnerStatus(partnerStatus);
    }
  }, [
    waitingRoom?.data,
    waitingRoom.isError,
    waitingRoom.isLoading,
    handlePartnerStatusChange,
  ]);

  return {
    status:
      waitingRoom.isError || user.isError
        ? "error"
        : waitingRoom.isLoading || user.isLoading || !socket || !partnerStatus
        ? "loading"
        : "ready",
    error: waitingRoom.error || user.error,
    user: user.data,
    partnerStatus,
    socket,
  };
};

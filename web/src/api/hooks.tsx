import { useQuery, UseQueryResult } from "react-query";
import { ApiError } from "./apiUtils";
import { getChatroom, getUser, getWaitingStatus } from "./api";

export const useUser = (): UseQueryResult<Record<string, unknown>, ApiError> =>
  useQuery(["user"], getUser);

export const useChatroom = (): UseQueryResult<
  Record<string, unknown>,
  ApiError
> => useQuery(["chatroom"], getChatroom);

export const useWaitingRoom = (): UseQueryResult<
  Record<string, unknown>,
  ApiError
> => useQuery(["waiting-room"], getWaitingStatus);

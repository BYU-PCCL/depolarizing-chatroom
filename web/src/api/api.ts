import { get } from "./apiUtils";

const CHATROOM_ENDPOINT = "chatroom";
const USER_ENDPOINT = "user";
const WAITING_STATUS_ENDPOINT = "waiting-status";

export const getChatroom = async () => get(CHATROOM_ENDPOINT);
export const getUser = async () => get(USER_ENDPOINT);
export const getWaitingStatus = async () => get(WAITING_STATUS_ENDPOINT);

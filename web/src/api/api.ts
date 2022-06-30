import { get } from "./apiUtils";

const CHATROOM_ENDPOINT = "chatroom";
const USER_ENDPOINT = "user";

export const getChatroom = async () => get(CHATROOM_ENDPOINT);
export const getUser = async () => get(USER_ENDPOINT);

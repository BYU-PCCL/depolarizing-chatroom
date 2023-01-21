import { ChatMessageState } from "../common/ChatMessage";

export interface Message {
  body: string;
  time?: number;
  state: ChatMessageState;
}

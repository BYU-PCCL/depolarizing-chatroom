import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./index.css";
import DeradicalizingChatroomApp from "./DeradicalizingChatroomApp";
import Modal from "react-modal";

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement
);

Modal.setAppElement("#root");

root.render(
  // <React.StrictMode>
  <BrowserRouter>
    <DeradicalizingChatroomApp />
  </BrowserRouter>
  // </React.StrictMode>
);

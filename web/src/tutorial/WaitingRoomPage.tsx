import React from "react";
import PageWidth from "../common/PageWidth";

function WaitingRoomPage() {
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

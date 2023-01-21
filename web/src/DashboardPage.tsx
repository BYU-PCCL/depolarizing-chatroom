import PageWidth from "./common/PageWidth";
import { useEffect, useState } from "react";
import { getEndpointUrl } from "./api/apiUtils";
import LoadingPage from "./common/LoadingPage";

interface StatsByPosition {
  supporters: number;
  opponents: number;
}

interface Stats {
  totalOnline: number;
  unmatched: StatsByPosition;
  prechat: StatsByPosition;
  inChatroom: StatsByPosition;
}

function DashboardPage() {
  // Every 5s, query the server for the latest user data
  const [stats, setStats] = useState<Stats | undefined>();

  useEffect(() => {
    const interval = setInterval(async () => {
      const response = await fetch(getEndpointUrl("stats"), {
        headers: {
          "Content-Type": "application/json",
        },
      });
      const data = await response.json();
      setStats(data);
    }, 800);
    return () => clearInterval(interval);
  });

  if (!stats) {
    return <LoadingPage />;
  }

  return (
    <PageWidth>
      <h2 className="text-3xl mb-4">Unmatched (waiting)</h2>
      <div>
        <p>Opponents: {stats.unmatched.opponents}</p>
        <p>Supporters: {stats.unmatched.supporters}</p>
      </div>
      <h2 className="text-3xl my-4">Pre-chat</h2>
      <div>
        <p>Opponents: {stats.prechat.opponents}</p>
        <p>Supporters: {stats.prechat.supporters}</p>
      </div>
      <h2 className="text-3xl my-4">In chatroom</h2>
      <div>
        <p>Opponents: {stats.inChatroom.opponents}</p>
        <p>Supporters: {stats.inChatroom.supporters}</p>
      </div>
    </PageWidth>
  );
}

export default DashboardPage;

import PageWidth from "./common/PageWidth";

function NoAuthPage() {
  return (
    <PageWidth>
      <span className="material-icons mb-8 text-6xl text-yellow-600">
        login
      </span>
      <h1 className="text-3xl mb-4">You're not logged in.</h1>
      <p>Complete a survey to get a link.</p>
    </PageWidth>
  );
}

export default NoAuthPage;

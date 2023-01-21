import PageWidth from "../common/PageWidth";

function ErrorPage({ error }: { error?: string }) {
  return (
    <PageWidth>
      <span className="material-icons mb-8 text-6xl text-red-600">
        error_outline
      </span>
      <h1 className="text-3xl mb-4">Something went wrong.</h1>
      <p>{error}</p>
    </PageWidth>
  );
}

export default ErrorPage;

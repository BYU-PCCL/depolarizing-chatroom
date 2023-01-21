function PageWidth({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex h-full flex-col items-center justify-center overflow-hidden bg-gray-50">
      <div className="w-full max-w-5xl p-4 sm:p-12 h-full flex flex-col items-start">
        {children}
      </div>
    </div>
  );
}

export default PageWidth;

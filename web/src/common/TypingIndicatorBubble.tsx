import "./ellipsis.css";
import { useEffect, useState } from "react";

function TypingIndicatorBubble({
  fill = "gray-500",
  background = "gray-200",
  visible = false,
}) {
  const [internallyVisible, setInternallyVisible] = useState(visible);

  useEffect(() => {
    if (!visible) {
      const timeout = setTimeout(() => {
        setInternallyVisible(visible);
      }, 200);
      return () => clearTimeout(timeout);
    } else {
      setInternallyVisible(visible);
    }
  }, [visible]);

  return (
    <div
      className={
        `w-14 h-7 rounded-full bg-${background} flex items-center justify-center ellipsis-container transition ease-out ` +
        (internallyVisible
          ? "translate-y-0 opacity-1"
          : "translate-y-2 opacity-0")
      }
    >
      <svg
        className={`w-10` + (internallyVisible ? " ellipsis" : "")}
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 48 24"
      >
        <circle cx="11" cy="12" r="4" className={`fill-${fill}`} />
        <circle cx="24" cy="12" r="4" className={`fill-${fill}`} />
        <circle cx="37" cy="12" r="4" className={`fill-${fill}`} />
      </svg>
    </div>
  );
}

export default TypingIndicatorBubble;

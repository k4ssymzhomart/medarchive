import { useEffect, useState } from "react";

export function useMediaQuery(query: string, fallback = true) {
  const [match, setMatch] = useState(fallback);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const update = () => setMatch(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, [query]);
  return match;
}

export const useIsDesktop = () => useMediaQuery("(min-width: 768px)");

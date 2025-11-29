"use client";

import { useEffect, useState } from "react";
import { isElectron } from "@/lib/electron";

/**
 * Returns true only after the Electron bridge has been detected on the client.
 * Initial render (server + first client pass) always returns false so SSR markup
 * matches the hydration payload.
 */
export function useIsElectronRuntime(): boolean {
  const [isElectronRuntime, setIsElectronRuntime] = useState(false);

  useEffect(() => {
    setIsElectronRuntime(isElectron());
  }, []);

  return isElectronRuntime;
}


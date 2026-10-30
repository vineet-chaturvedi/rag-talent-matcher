"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/**
 * Re-render the current page's Server Components every `seconds`, while the tab is visible.
 *
 * `router.refresh()` asks the server for fresh Server Component output and merges it in place:
 * no full reload, scroll position and open menus stay as they are. The dashboard mounts this only
 * while resumes are still being processed, so an idle portal makes no requests at all.
 */
export function AutoRefresh({ seconds = 10 }: { seconds?: number }) {
  const router = useRouter();
  useEffect(() => {
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") router.refresh();
    }, seconds * 1000);
    return () => window.clearInterval(id);
  }, [router, seconds]);
  return null;
}

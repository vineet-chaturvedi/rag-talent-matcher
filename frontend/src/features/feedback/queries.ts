import "server-only";

import { request } from "@/lib/api/client";
import type { FeedbackRating, FeedbackTarget } from "@/lib/api/types";

export const FEEDBACK_PAGE_SIZE = 50;

/** Every rating with its context, newest first (admins only: FastAPI answers 403 to anyone else). */
export const listFeedback = (target?: FeedbackTarget, rating?: FeedbackRating, page = 1) =>
  request((api) =>
    api.GET("/api/feedback", {
      params: { query: { target, rating, limit: FEEDBACK_PAGE_SIZE + 1, offset: (page - 1) * FEEDBACK_PAGE_SIZE } },
    }),
  );

import "server-only";

import { request } from "@/lib/api/client";

/** All portal accounts (admins only: FastAPI answers 403 to anyone else). */
export const listUsers = () => request((api) => api.GET("/api/users"));

import { getCurrentUser } from "@/lib/auth/session";
import { firstName } from "@/lib/utils";

/** "Good to see you, Priya". Needs the session, so the page shows plain "Dashboard" until it streams in. */
export async function Greeting() {
  const user = await getCurrentUser();
  const name = firstName(user.fullName);
  return <>{name ? `Good to see you, ${name}` : "Dashboard"}</>;
}

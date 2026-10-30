import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ActionButton } from "@/components/action-button";
import { getCurrentUser } from "@/lib/auth/session";
import { formatDate } from "@/lib/utils";

import { setUserActive, setUserRole } from "../actions";
import { listUsers } from "../queries";
import { ROLE_LABEL } from "../schemas";
import { ResetPasswordDialog } from "./reset-password-dialog";

/**
 * Every portal account. Accounts are never deleted: deactivating keeps the history ("who ran this
 * match?", "who uploaded this resume?") and can be undone. Your own row has no role/deactivate
 * buttons (the backend refuses those changes to yourself too, so nobody locks themselves out).
 */
export async function UsersTable() {
  const [result, me] = await Promise.all([listUsers(), getCurrentUser()]);
  if (!result.ok) return <Alert>{result.message}</Alert>;
  const users = [...result.data].sort(
    (a, b) => Number(b.is_active) - Number(a.is_active) || a.full_name.localeCompare(b.full_name),
  );

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Person</TableHead>
          <TableHead>Role</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Created</TableHead>
          <TableHead>
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {users.map((user) => {
          const isMe = user.id === me.id;
          return (
            <TableRow key={user.id} className={user.is_active ? undefined : "opacity-60"}>
              <TableCell>
                <span className="font-medium">{user.full_name}</span>
                {isMe && (
                  <Badge tone="info" className="ml-2">
                    you
                  </Badge>
                )}
                <span className="block text-xs text-muted-foreground">{user.email}</span>
              </TableCell>
              <TableCell>
                <Badge tone={user.role === "admin" ? "info" : "neutral"}>{ROLE_LABEL[user.role]}</Badge>
              </TableCell>
              <TableCell>
                <Badge tone={user.is_active ? "success" : "neutral"}>{user.is_active ? "Active" : "Deactivated"}</Badge>
              </TableCell>
              <TableCell className="text-xs whitespace-nowrap text-muted-foreground">
                {formatDate(user.created_at)}
              </TableCell>
              <TableCell>
                {isMe ? (
                  <span className="text-xs text-muted-foreground">Change your password on the Account page</span>
                ) : (
                  <div className="flex flex-wrap justify-end gap-1">
                    {user.is_active && <ResetPasswordDialog userId={user.id} name={user.full_name} />}
                    {user.is_active &&
                      (user.role === "admin" ? (
                        <ActionButton
                          action={setUserRole.bind(null, user.id, "resource_manager")}
                          label="Make resource manager"
                          pendingLabel="Saving…"
                          variant="ghost"
                        />
                      ) : (
                        <ActionButton
                          action={setUserRole.bind(null, user.id, "admin")}
                          label="Make admin"
                          pendingLabel="Saving…"
                          variant="ghost"
                          confirm={{
                            title: `Make ${user.full_name} an administrator?`,
                            description:
                              "Administrators can upload and delete resumes, re-process the knowledge base and manage every account, including yours.",
                            confirmLabel: "Make admin",
                          }}
                        />
                      ))}
                    {user.is_active ? (
                      <ActionButton
                        action={setUserActive.bind(null, user.id, false)}
                        label="Deactivate"
                        pendingLabel="Saving…"
                        variant="ghost"
                        confirm={{
                          title: `Deactivate ${user.full_name}?`,
                          description:
                            "They can no longer sign in. Their history (match runs, uploads) is kept, and you can reactivate them later. A session they already have ends at their next action.",
                          confirmLabel: "Deactivate",
                        }}
                      />
                    ) : (
                      <ActionButton
                        action={setUserActive.bind(null, user.id, true)}
                        label="Reactivate"
                        pendingLabel="Saving…"
                      />
                    )}
                  </div>
                )}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

export function UsersTableSkeleton() {
  return (
    <div className="space-y-3" role="status" aria-label="Loading users">
      {Array.from({ length: 4 }, (_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

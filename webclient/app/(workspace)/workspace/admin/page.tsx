"use client";

import { useEffect, useState } from "react";

import Alertdialog from "@/components/Alertdialog";
import { useRouter } from "next/navigation";
import { useGetCurrentUser } from "@/services/auth";
import { Button } from "@/components/ui/button";
import {
  useDeleteUser,
  useListUsers,
  useUpdateUserActivation,
  useUpdateUserRole,
} from "@/services/user";
import { toast } from "@/components/ui/toast";
import { getStoredToken } from "@/utils/auth-storage";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import CreateOrEdit from "./_partials/createOrEdit";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function AdminPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState<{
    type: "deactivate" | "delete";
    id: string;
  } | null>(null);
  const me = useGetCurrentUser(token);
  const users = useListUsers();
  const updateUser = useUpdateUserActivation();
  const updateRole = useUpdateUserRole();
  const deleteUser = useDeleteUser();

  useEffect(() => setToken(getStoredToken("peka_access_token") ?? ""), []);
  useEffect(() => {
    if (me.data && me.data.role !== "admin") router.replace("/workspace");
  }, [me.data, router]);

  function confirmActionSubmit() {
    if (!confirmAction) return;
    const userEmail = selectedUser?.email ?? "User";
    if (confirmAction.type === "delete") {
      deleteUser.mutate(confirmAction.id, {
        onSuccess: () => toast.add({ title: `${userEmail} deleted.`, type: "success" }),
        onError: () => toast.add({ title: "Unable to delete user.", type: "error" }),
        onSettled: () => setConfirmAction(null),
      });
      return;
    }
    updateUser.mutate(
      { id: confirmAction.id, is_active: false },
      {
        onSuccess: () => toast.add({ title: `${userEmail} deactivated.`, type: "success" }),
        onError: () => toast.add({ title: "Unable to deactivate user.", type: "error" }),
        onSettled: () => setConfirmAction(null),
      },
    );
  }
  function activateUser(id: string, email: string) {
    updateUser.mutate(
      { id, is_active: true },
      {
        onSuccess: () => toast.add({ title: `${email} activated.`, type: "success" }),
        onError: () => toast.add({ title: "Unable to activate user.", type: "error" }),
      },
    );
  }

  const selectedUser = users.data?.find((user) => user.id === confirmAction?.id);

  if (!me.data || me.data.role !== "admin") return null;

  return (
    <section className="mx-auto max-w-5xl space-y-8 p-6 lg:p-10">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">User management</h1>
          <p className="mt-1 text-sm text-muted">Create and manage workspace users.</p>
        </div>
        <div className="flex gap-2">
          <Button
            className="border-border"
            type="button"
            variant="outline"
            onClick={() => router.push("/workspace/admin/settings")}
          >
            Workspace settings
          </Button>
          <Button className="px-4 py-2" type="button" onClick={() => setAddOpen(true)}>
            Add user
          </Button>
        </div>
      </div>
      <CreateOrEdit open={addOpen} onOpenChange={setAddOpen} />

      <Alertdialog
        open={confirmAction !== null}
        onOpenChange={(open) => !open && setConfirmAction(null)}
        title={confirmAction?.type === "delete" ? "Delete user?" : "Deactivate user?"}
        description={
          confirmAction?.type === "delete"
            ? `Permanently delete ${selectedUser?.email ?? "this user"}?`
            : `Deactivate ${selectedUser?.email ?? "this user"}?`
        }
        confirmLabel={confirmAction?.type === "delete" ? "Delete" : "Deactivate"}
        onConfirm={confirmActionSubmit}
        pending={deleteUser.isPending || updateUser.isPending}
      />

      {users.isLoading ? (
        <p className="text-sm text-muted">Loading users...</p>
      ) : users.isError ? (
        <p className="text-sm text-danger">Unable to load users.</p>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-border bg-background shadow-sm">
          <Table>
            <TableHeader className="bg-secondary/70">
              <TableRow className="border-border hover:bg-secondary/70">
                <TableHead className="px-5 py-4 text-xs uppercase tracking-[0.14em] text-muted">
                  Email
                </TableHead>
                <TableHead className="px-5 py-4 text-xs uppercase tracking-[0.14em] text-muted">
                  Role
                </TableHead>
                <TableHead className="px-5 py-4 text-xs uppercase tracking-[0.14em] text-muted">
                  Status
                </TableHead>
                <TableHead className="px-5 py-4 text-center text-xs uppercase tracking-[0.14em] text-muted">
                  Actions
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.data?.map((user) => (
                <TableRow key={user.id} className="border-border hover:bg-secondary/40">
                  <TableCell className="px-5 py-4 font-medium text-foreground">
                    {user.display_name && <div>{user.display_name}</div>}
                    <div className={user.display_name ? "text-xs font-normal text-muted" : ""}>
                      {user.email}
                    </div>
                  </TableCell>
                  <TableCell className="px-5 py-4">
                    <Select
                      value={user.role}
                      disabled={user.id === me.data.id || updateRole.isPending}
                      onValueChange={(role) =>
                        updateRole.mutate(
                          { id: user.id, role: role as typeof user.role },
                          {
                            onSuccess: () => toast.add({ title: "User role updated.", type: "success" }),
                            onError: () => toast.add({ title: "Unable to update user role.", type: "error" }),
                          },
                        )
                      }
                    >
                      <SelectTrigger aria-label={`Role for ${user.email}`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="staff">Staff</SelectItem>
                        <SelectItem value="senior">Senior</SelectItem>
                        <SelectItem value="admin">Admin</SelectItem>
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell className="px-5 py-4">
                    <span
                      className={
                        user.is_active
                          ? "rounded-full bg-success px-2.5 py-1 text-xs font-medium text-success-foreground"
                          : "rounded-full bg-danger/15 px-2.5 py-1 text-xs font-medium text-danger"
                      }
                    >
                      {user.is_active ? "Active" : "Inactive"}
                    </span>
                  </TableCell>
                  <TableCell className="space-x-2 px-5 py-4 text-center">
                    <Button
                      className="border-border hover:bg-secondary"
                      disabled={updateUser.isPending || user.id === me.data.id}
                      onClick={() =>
                        user.is_active
                          ? setConfirmAction({ type: "deactivate", id: user.id })
                          : activateUser(user.id, user.email)
                      }
                      type="button"
                      variant="outline"
                    >
                      {user.is_active ? "Deactivate" : "Activate"}
                    </Button>
                    {!user.is_active && (
                      <Button
                        className="px-4 py-2.5"
                        disabled={deleteUser.isPending}
                        onClick={() => setConfirmAction({ type: "delete", id: user.id })}
                        type="button"
                        variant="destructive"
                      >
                        Delete
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  );
}

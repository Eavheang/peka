"use client";

import { Controller, useForm } from "react-hook-form";
import { toast } from "@/components/ui/toast";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { UserRole } from "@/interface/auth";
import { useCreateUser } from "@/services/user";

type CreateUserValues = { email: string; display_name: string; password: string; role: UserRole };
type CreateOrEditProps = { open: boolean; onOpenChange: (open: boolean) => void };

export default function CreateOrEdit({ open, onOpenChange }: CreateOrEditProps) {
  const createUser = useCreateUser();
  const { control, register, handleSubmit, reset } = useForm<CreateUserValues>({
    defaultValues: { email: "", display_name: "", password: "", role: "staff" },
  });

  function close(nextOpen: boolean) {
    if (!nextOpen) reset();
    onOpenChange(nextOpen);
  }

  function submit(values: CreateUserValues) {
    createUser.mutate(values, {
      onSuccess: () => {
        toast.add({ title: "User created.", type: "success" });
        close(false);
      },
      onError: () => toast.add({ title: "Unable to create user.", type: "error" }),
    });
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="w-[calc(100%-2rem)] max-w-md gap-0 overflow-hidden rounded-2xl border-border bg-panel p-0 text-panel-foreground shadow-2xl">
        <div className="p-6">
          <DialogTitle className="text-lg font-semibold tracking-tight text-panel-foreground">
            Add user
          </DialogTitle>
          <DialogDescription className="mt-2 text-sm leading-6 text-panel-foreground/70">
            Create a new workspace user.
          </DialogDescription>
        </div>
        <form
          className="grid gap-3 border-t border-panel-foreground/15 p-6"
          onSubmit={handleSubmit(submit)}
        >
          <Input type="email" aria-label="Email" placeholder="Email" {...register("email", { required: true })} />
          <Input
            aria-label="Name"
            placeholder="Name (optional)"
            maxLength={100}
            {...register("display_name")}
          />
          <Input
            type="password"
            placeholder="Password (12+ characters)"
            minLength={12}
            {...register("password", { required: true, minLength: 12 })}
          />
          <Controller
            control={control}
            name="role"
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger>
                  <SelectValue placeholder="Select role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectLabel>Role</SelectLabel>
                    <SelectItem value="staff">Staff</SelectItem>
                    <SelectItem value="senior">Senior</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            )}
          />
          <Button
            className="mt-2 px-5 py-3 text-base"
            disabled={createUser.isPending}
            type="submit"
          >
            {createUser.isPending ? "Creating..." : "Create user"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

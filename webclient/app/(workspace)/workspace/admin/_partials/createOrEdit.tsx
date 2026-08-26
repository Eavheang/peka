"use client";

import { Controller, useForm } from "react-hook-form";
import { toast } from "@/components/ui/toast";

import DialogContext from "@/components/DialogContext";
import { Button } from "@/components/ui/button";
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

type CreateUserValues = { email: string; password: string; role: UserRole };
type CreateOrEditProps = { open: boolean; onOpenChange: (open: boolean) => void };

export default function CreateOrEdit({ open, onOpenChange }: CreateOrEditProps) {
  const createUser = useCreateUser();
  const { control, register, handleSubmit, reset } = useForm<CreateUserValues>({
    defaultValues: { email: "", password: "", role: "staff" },
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
    <DialogContext
      open={open}
      onOpenChange={close}
      title="Add user"
      description="Create a new workspace user."
      onSubmit={handleSubmit(submit)}
    >
      <Input type="email" placeholder="Email" {...register("email", { required: true })} />
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
      <Button className="mt-2 px-5 py-3 text-base" disabled={createUser.isPending} type="submit">
        {createUser.isPending ? "Creating..." : "Create user"}
      </Button>
    </DialogContext>
  );
}

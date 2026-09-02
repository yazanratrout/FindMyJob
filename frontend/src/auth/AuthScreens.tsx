import { type FormEvent, useState } from "react";
import { useLogin, useSetup } from "@/api/hooks";
import { ApiError } from "@/api/client";
import { Button, Card, ErrorBox, Input } from "@/components/ui";

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center text-xl font-bold">FindMyJob</div>
        <Card>{children}</Card>
      </div>
    </div>
  );
}

export function SetupScreen() {
  const setup = useSetup();
  const [pass, setPass] = useState("");
  const [confirm, setConfirm] = useState("");

  const mismatch = confirm.length > 0 && pass !== confirm;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (pass.length >= 8 && pass === confirm) setup.mutate(pass);
  };

  return (
    <Shell>
      <form onSubmit={submit} className="space-y-3">
        <p className="text-sm text-slate-600">
          Set a passphrase to protect this installation (at least 8 characters).
        </p>
        <Input
          type="password"
          placeholder="Passphrase"
          value={pass}
          onChange={(e) => setPass(e.target.value)}
          autoFocus
        />
        <Input
          type="password"
          placeholder="Confirm passphrase"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        {mismatch && <ErrorBox message="Passphrases don't match." />}
        {setup.error && (
          <ErrorBox
            message={
              setup.error instanceof ApiError
                ? setup.error.message
                : "Something went wrong."
            }
          />
        )}
        <Button
          type="submit"
          className="w-full"
          disabled={pass.length < 8 || pass !== confirm || setup.isPending}
        >
          {setup.isPending ? "Setting up…" : "Continue"}
        </Button>
      </form>
    </Shell>
  );
}

export function LoginScreen() {
  const login = useLogin();
  const [pass, setPass] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (pass) login.mutate(pass);
  };

  return (
    <Shell>
      <form onSubmit={submit} className="space-y-3">
        <Input
          type="password"
          placeholder="Passphrase"
          value={pass}
          onChange={(e) => setPass(e.target.value)}
          autoFocus
        />
        {login.error && (
          <ErrorBox
            message={
              login.error instanceof ApiError
                ? login.error.message
                : "Login failed."
            }
          />
        )}
        <Button type="submit" className="w-full" disabled={!pass || login.isPending}>
          {login.isPending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </Shell>
  );
}

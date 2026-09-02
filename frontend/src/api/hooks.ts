import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";

export interface AuthStatus {
  configured: boolean;
  authenticated: boolean;
}

export interface Health {
  status: string;
  version: string;
  db_ok: boolean;
}

export interface RunSummary {
  id: number;
  trigger: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  stats: Record<string, unknown>;
  error_count: number;
}

export interface Costs {
  month: string;
  cost_eur: number;
  budget_eur: number;
  remaining_eur: number;
  projected_month_end_eur: number;
  calls: number;
}

export const authKeys = { status: ["auth", "status"] as const };

export function useAuthStatus() {
  return useQuery({
    queryKey: authKeys.status,
    queryFn: () => api.get<AuthStatus>("/auth/status"),
  });
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.get<Health>("/health"),
  });
}

export function useRuns() {
  return useQuery({
    queryKey: ["runs"],
    queryFn: () => api.get<RunSummary[]>("/runs"),
  });
}

export function useCosts() {
  return useQuery({ queryKey: ["costs"], queryFn: () => api.get<Costs>("/costs") });
}

export function useSetup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (passphrase: string) =>
      api.post<AuthStatus>("/auth/setup", { passphrase }),
    onSuccess: () => qc.invalidateQueries({ queryKey: authKeys.status }),
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (passphrase: string) =>
      api.post<AuthStatus>("/auth/login", { passphrase }),
    onSuccess: () => qc.invalidateQueries({ queryKey: authKeys.status }),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/auth/logout"),
    onSuccess: () => qc.clear(),
  });
}

export function useTriggerRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body?: { fetch_only?: boolean; no_llm?: boolean }) =>
      api.post<RunSummary>("/runs", body ?? {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });
}

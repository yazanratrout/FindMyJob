import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  AuthStatus,
  Costs,
  CoverLetter,
  CoverLetterContent,
  DocumentRead,
  DocumentType,
  Health,
  JobDetail,
  JobList,
  KeywordSuggestions,
  ParseResult,
  Profile,
  ProfileUpdate,
  RunSummary,
  SemesterTerm,
  Settings,
  Skill,
  SettingsUpdate,
} from "./types";

export type {
  AuthStatus,
  Costs,
  DocumentRead,
  Health,
  Profile,
  RunSummary,
  Settings,
} from "./types";

const keys = {
  auth: ["auth", "status"] as const,
  profile: ["profile"] as const,
  documents: ["documents"] as const,
  settings: ["settings"] as const,
  terms: ["semester-terms"] as const,
  runs: ["runs"] as const,
  costs: ["costs"] as const,
};

// ---- auth ------------------------------------------------------------
export function useAuthStatus() {
  return useQuery({ queryKey: keys.auth, queryFn: () => api.get<AuthStatus>("/auth/status") });
}

export function useSetup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (passphrase: string) => api.post<AuthStatus>("/auth/setup", { passphrase }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.auth }),
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (passphrase: string) => api.post<AuthStatus>("/auth/login", { passphrase }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.auth }),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/auth/logout"),
    onSuccess: () => qc.clear(),
  });
}

// ---- misc ----------------------------------------------------------
export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: () => api.get<Health>("/health") });
}

export function useRuns() {
  return useQuery({ queryKey: keys.runs, queryFn: () => api.get<RunSummary[]>("/runs") });
}

export function useCosts() {
  return useQuery({ queryKey: keys.costs, queryFn: () => api.get<Costs>("/costs") });
}

export function useTriggerRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body?: { fetch_only?: boolean; no_llm?: boolean }) =>
      api.post<RunSummary>("/runs", body ?? {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.runs }),
  });
}

// ---- documents ----------------------------------------------------
export function useDocuments() {
  return useQuery({
    queryKey: keys.documents,
    queryFn: () => api.get<DocumentRead[]>("/documents"),
  });
}

export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ type, file }: { type: DocumentType; file: File }) => {
      const form = new FormData();
      form.set("type", type);
      form.set("file", file);
      return api.upload<DocumentRead>("/documents", form);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.documents }),
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.del<void>(`/documents/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.documents }),
  });
}

// ---- profile ------------------------------------------------------
export function useProfile() {
  return useQuery({ queryKey: keys.profile, queryFn: () => api.get<Profile>("/profile") });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: ProfileUpdate) => api.put<Profile>("/profile", patch),
    onSuccess: (data) => qc.setQueryData(keys.profile, data),
  });
}

export function useParseProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<ParseResult>("/profile/parse"),
    onSuccess: (data) => qc.setQueryData(keys.profile, data.profile),
  });
}

export function useUpdateSkills() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (skills: Array<Omit<Skill, "id" | "source">>) =>
      api.put<Skill[]>("/profile/skills", skills),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.profile }),
  });
}

// ---- settings ----------------------------------------------------
export function useSettings() {
  return useQuery({ queryKey: keys.settings, queryFn: () => api.get<Settings>("/settings") });
}

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: SettingsUpdate) => api.put<Settings>("/settings", patch),
    onSuccess: (data) => qc.setQueryData(keys.settings, data),
  });
}

export function useSuggestKeywords() {
  return useMutation({
    mutationFn: (body: { target_fields: string[]; target_titles: string[] }) =>
      api.post<KeywordSuggestions>("/settings/suggest-keywords", body),
  });
}

// ---- semester terms -------------------------------------------
export function useSemesterTerms() {
  return useQuery({ queryKey: keys.terms, queryFn: () => api.get<SemesterTerm[]>("/semester-terms") });
}

export function useAddTerm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { label: string; lecture_start: string; lecture_end: string }) =>
      api.post<SemesterTerm>("/semester-terms", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.terms }),
  });
}

export function useDeleteTerm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.del<void>(`/semester-terms/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.terms }),
  });
}

// ---- jobs ---------------------------------------------------------
export interface JobFilters {
  bucket?: string;
  source?: string;
  search?: string;
}

export function useJobs(filters: JobFilters) {
  const params = new URLSearchParams();
  if (filters.bucket) params.set("bucket", filters.bucket);
  if (filters.source) params.set("source", filters.source);
  if (filters.search) params.set("search", filters.search);
  const qs = params.toString();
  return useQuery({
    queryKey: ["jobs", filters],
    queryFn: () => api.get<JobList>(`/jobs${qs ? `?${qs}` : ""}`),
  });
}

export function useJobDetail(id: number | null) {
  return useQuery({
    queryKey: ["job", id],
    queryFn: () => api.get<JobDetail>(`/jobs/${id}`),
    enabled: id != null,
  });
}

// ---- cover letters ---------------------------------------------
export function useCoverLetters(jobId: number | null) {
  return useQuery({
    queryKey: ["cover-letters", jobId],
    queryFn: () => api.get<CoverLetter[]>(`/jobs/${jobId}/cover-letters`),
    enabled: jobId != null,
  });
}

export function useGenerateCoverLetter(jobId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<CoverLetter>(`/jobs/${jobId}/cover-letter`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cover-letters", jobId] }),
  });
}

export function useUpdateCoverLetter(jobId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, content }: { id: number; content: CoverLetterContent }) =>
      api.put<CoverLetter>(`/cover-letters/${id}`, { content }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cover-letters", jobId] }),
  });
}

export function useRegenerateCoverLetter(jobId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, instruction }: { id: number; instruction?: string }) =>
      api.post<CoverLetter>(`/cover-letters/${id}/regenerate`, { instruction }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cover-letters", jobId] }),
  });
}

export function downloadCoverLetter(id: number) {
  return api.downloadFile(`/cover-letters/${id}/docx`);
}

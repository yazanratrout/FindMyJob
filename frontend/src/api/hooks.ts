import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  Application,
  ApplicationStatus,
  AuthStatus,
  CalibrationReport,
  Costs,
  CoverLetter,
  CoverLetterContent,
  Digest,
  DocumentRead,
  DocumentType,
  EligibilityEntry,
  EligibilityGauge,
  FeedbackVerdict,
  Health,
  JobDetail,
  JobList,
  KeywordSuggestions,
  ParseResult,
  Profile,
  ProfileUpdate,
  RunDetail,
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

/**
 * The most recent run, polled fast while it is in progress so the whole app can
 * show live pipeline status (and refresh job lists when it lands).
 */
export function useLatestRun() {
  const qc = useQueryClient();
  return useQuery({
    queryKey: ["runs", "latest"],
    queryFn: async () => {
      const runs = await api.get<RunSummary[]>("/runs?limit=1");
      const run = runs[0] ?? null;
      if (run && run.status !== "running") {
        // a run just finished -> pull in the jobs/digests it produced
        qc.invalidateQueries({ queryKey: ["jobs"] });
        qc.invalidateQueries({ queryKey: ["digests"] });
      }
      return run;
    },
    refetchInterval: (query) => (query.state.data?.status === "running" ? 2000 : 20_000),
  });
}

export function useRunDetail(id: number | null) {
  return useQuery({
    queryKey: ["run", id],
    queryFn: () => api.get<RunDetail>(`/runs/${id}`),
    enabled: id != null,
    refetchInterval: (query) =>
      ["completed", "failed"].includes(query.state.data?.run.status ?? "")
        ? false
        : 1500,
  });
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

export function useSetJobFeedback(jobId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (verdict: FeedbackVerdict) =>
      api.put<{ job_id: number; verdict: string; note: string }>(
        `/jobs/${jobId}/feedback`,
        { verdict },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job", jobId] });
      qc.invalidateQueries({ queryKey: ["calibration"] });
    },
  });
}

export function useClearJobFeedback(jobId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.del<void>(`/jobs/${jobId}/feedback`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job", jobId] });
      qc.invalidateQueries({ queryKey: ["calibration"] });
    },
  });
}

// ---- calibration ---------------------------------------------
export function useCalibration() {
  return useQuery({
    queryKey: ["calibration"],
    queryFn: () => api.get<CalibrationReport>("/calibration"),
  });
}

export function useApplyCalibration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<CalibrationReport>("/calibration/apply"),
    onSuccess: (data) => {
      qc.setQueryData(["calibration"], data);
      qc.invalidateQueries({ queryKey: keys.settings });
    },
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

// ---- applications --------------------------------------------
export interface ApplicationPatch {
  status?: ApplicationStatus;
  applied_at?: string | null;
  follow_up_at?: string | null;
  outcome_note?: string;
  documents_used?: string[];
}

export function useApplications() {
  return useQuery({
    queryKey: ["applications"],
    queryFn: () => api.get<Application[]>("/applications"),
  });
}

export function useFollowUps() {
  return useQuery({
    queryKey: ["follow-ups"],
    queryFn: () => api.get<Application[]>("/applications/follow-ups"),
  });
}

function invalidateApplications(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["applications"] });
  qc.invalidateQueries({ queryKey: ["follow-ups"] });
  qc.invalidateQueries({ queryKey: ["job"] });
}

export function useCreateApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (job_id: number) => api.post<Application>("/applications", { job_id }),
    onSuccess: () => invalidateApplications(qc),
  });
}

export function useUpdateApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: ApplicationPatch }) =>
      api.put<Application>(`/applications/${id}`, patch),
    onSuccess: () => invalidateApplications(qc),
  });
}

// ---- digests -------------------------------------------------
export function useDigests() {
  return useQuery({
    queryKey: ["digests"],
    queryFn: () => api.get<Digest[]>("/digests"),
  });
}

export function useUnseenDigestCount() {
  return useQuery({
    queryKey: ["digests", "unseen"],
    queryFn: () => api.get<{ count: number }>("/digests/unseen-count"),
    refetchInterval: 30_000,
  });
}

export function useMarkDigestsSeen() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/digests/seen"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["digests"] }),
  });
}

// ---- eligibility --------------------------------------------
export function useEligibilityGauge() {
  return useQuery({
    queryKey: ["eligibility"],
    queryFn: () => api.get<EligibilityGauge>("/eligibility"),
  });
}

export function useEligibilityEntries() {
  return useQuery({
    queryKey: ["eligibility", "entries"],
    queryFn: () => api.get<EligibilityEntry[]>("/eligibility/entries"),
  });
}

function invalidateEligibility(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["eligibility"] });
}

export function useAddEligibilityEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      period_start: string;
      period_end: string;
      day_type: "full" | "half";
      note: string;
    }) => api.post<EligibilityEntry>("/eligibility/entries", body),
    onSuccess: () => invalidateEligibility(qc),
  });
}

export function useDeleteEligibilityEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.del<void>(`/eligibility/entries/${id}`),
    onSuccess: () => invalidateEligibility(qc),
  });
}

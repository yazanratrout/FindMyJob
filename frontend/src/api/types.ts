export interface AuthStatus {
  configured: boolean;
  authenticated: boolean;
}

export interface Health {
  status: string;
  version: string;
  db_ok: boolean;
}

export type DocumentType =
  | "cv"
  | "enrollment"
  | "transcript"
  | "reference"
  | "portfolio"
  | "other";

export interface DocumentRead {
  id: number;
  type: DocumentType;
  filename: string;
  mime: string;
  size_bytes: number;
  parse_status: "pending" | "done" | "failed";
  parse_error: string | null;
  text_chars: number;
  uploaded_at: string;
}

export interface Skill {
  id: number;
  name: string;
  category: "language" | "technical" | "tool" | "domain" | "soft";
  proficiency: number;
  years: number | null;
  source: string;
  evidence: string;
}

export interface Profile {
  id: number;
  full_name: string;
  email: string;
  phone: string;
  street: string;
  postal_code: string;
  city: string;
  country: string;
  nationality: string;
  is_eu_eea: boolean;
  university: string;
  program: string;
  degree_level: "bachelor" | "master" | "phd" | null;
  current_semester: number | null;
  enrollment_valid_until: string | null;
  expected_graduation: string | null;
  voice_sample_text: string;
  locked_fields: string[];
  has_structured_parse: boolean;
  skills: Skill[];
}

export type ProfileUpdate = Partial<
  Pick<
    Profile,
    | "full_name"
    | "email"
    | "phone"
    | "street"
    | "postal_code"
    | "city"
    | "country"
    | "nationality"
    | "is_eu_eea"
    | "university"
    | "program"
    | "degree_level"
    | "current_semester"
    | "voice_sample_text"
  >
>;

export interface Settings {
  target_city: string;
  target_lat: number | null;
  target_lon: number | null;
  radius_km: number;
  allow_remote: boolean;
  target_fields: string[];
  target_titles: string[];
  keywords_allow: string[];
  keywords_block: string[];
  job_types: string[];
  recency_days: number;
  language_max_cefr: string;
  language_hard: boolean;
  hours_max: number;
  hours_hard: boolean;
  contract_types: string[];
  contract_type_hard: boolean;
  score_threshold_recommend: number;
  score_threshold_maybe: number;
  weights: Record<string, number>;
  blend_soft_ratio: number;
  run_time: string;
  run_timezone: string;
  notify_channels: string[];
  notify_email: string | null;
  notify_telegram_chat_id: string | null;
  digest_top_n: number;
  cover_letter_language_mode: "match_posting" | "always_de" | "always_en";
  cover_letter_tone: string;
  sources_enabled: Record<string, boolean>;
  eligibility_module_enabled: boolean;
  retention_days: number;
  repost_days: number;
  onboarding_completed: boolean;
}

export type SettingsUpdate = Partial<Omit<Settings, "target_lat" | "target_lon">>;

export interface KeywordSuggestions {
  core: string[];
  adjacent: string[];
  tools: string[];
  likely_noise: string[];
}

export interface SemesterTerm {
  id: number;
  label: string;
  lecture_start: string;
  lecture_end: string;
}

export interface ParseResult {
  profile: Profile;
  tokens_in: number;
  tokens_out: number;
  cost_eur: number;
  cache_hit: boolean;
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

import { api, API_BASE } from "./client";

export type LeaderboardEntry = {
  rank: number;
  nickname: string;
  public_id: string;
  sessions_count: number;
  personality_summary: string;
  total_score: number;
};

export function getLeaderboard(period: "all" | "weekly" = "weekly") {
  return api<{ period: string; items: LeaderboardEntry[] }>(
    `/api/v1/leaderboard?period=${period}`,
  );
}

export type AdminStats = {
  total_users: number;
  survey_completion_rate: number;
  valid_rounds: number;
  avg_coop_rate: number;
};

export type AdminUser = {
  id: number;
  nickname: string;
  public_id: string;
  email: string;
  role: string;
  total_score: number;
  sessions_count: number;
  personality_summary: string;
  survey_status: string;
  quality_passed: boolean | null;
  has_personality: boolean;
  status: string;
  can_retake_survey: boolean;
  retake_count: number;
  retake_block_reason: string | null;
  has_submitted_survey: boolean;
  quality_review_status: string | null;
  quality_soft_flags: string[];
  quality_hard_exclusion: boolean;
};

export type SurveyQualityReview = {
  user_id: number;
  response_id: number;
  quality_passed: boolean | null;
  quality_flags: Record<string, unknown> | null;
  attention_answers: Record<string, number>;
  diligence_answers: Record<string, number>;
  page_timings_seconds: Record<string, number>;
  blur_count: number;
  hard_exclusion: boolean;
  hard_exclusion_reasons: string[];
  soft_flags: string[];
  review_status: string;
  review_reason: string | null;
};

export type AdminPersonality = {
  user_id: number;
  nickname: string;
  public_id: string;
  summary_label: string;
  scores: Record<string, number>;
  dimensions: {
    code: string;
    name: string;
    english: string;
    score: number;
    general: string;
    band_text: string;
  }[];
  quality_passed?: boolean | null;
};

export type AdminScene = {
  id: number;
  scene_key: string;
  no: string;
  title: string;
  short_desc: string;
  option_a: string;
  option_b: string;
  option_a_text: string;
  option_b_text: string;
  required: boolean;
  enabled: boolean;
  sort_order: number;
};

export type AdminExperiment = {
  id: number;
  code: string;
  title: string;
  status: string;
  sort_order: number;
  rounds_per_scene: number;
  scenes: AdminScene[];
};

export type InviteCode = {
  id: number;
  code: string;
  kind: string;
  max_uses: number;
  used_count: number;
  enabled: boolean;
  note: string;
  owner_id?: number | null;
  owner_nickname?: string | null;
  created_at?: string;
};

export type SubAdmin = {
  id: number;
  nickname: string;
  email: string;
  public_id: string;
  status: "active" | "disabled" | string;
  invite_code?: string | null;
  invite_code_id?: number | null;
  owned_invite_count?: number;
  created_at?: string | null;
};

export type AccountEvent = {
  id: number;
  event_type: string;
  title?: string;
  detail: string;
  user_id: number | null;
  actor_id: number | null;
  created_at?: string;
};

export function getAdminStats() {
  return api<AdminStats>("/api/v1/admin/stats/overview");
}

export function getAdminUsers(q?: string) {
  const qs = q ? `?q=${encodeURIComponent(q)}` : "";
  return api<{ total: number; items: AdminUser[] }>(`/api/v1/admin/users${qs}`);
}

export function getAdminPersonality(userId: number) {
  return api<AdminPersonality>(`/api/v1/admin/users/${userId}/personality`);
}

export function setUserStatus(userId: number, status: "active" | "disabled") {
  return api<{ ok: boolean }>(`/api/v1/admin/users/${userId}/status`, {
    method: "PATCH",
    json: { status },
  });
}

export function resetUserPassword(userId: number, new_password: string) {
  return api<{ ok: boolean }>(`/api/v1/admin/users/${userId}/reset-password`, {
    method: "POST",
    json: { new_password },
  });
}

export function allowSurveyRetake(userId: number) {
  return api<{ ok: boolean; retake_count: number }>(
    `/api/v1/admin/users/${userId}/allow-survey-retake`,
    { method: "POST" },
  );
}

export function getSurveyQualityReview(userId: number) {
  return api<SurveyQualityReview>(`/api/v1/admin/users/${userId}/survey-quality`);
}

export function reviewSurveyQuality(
  userId: number,
  status: "kept" | "excluded",
  reason: string,
) {
  return api<SurveyQualityReview>(`/api/v1/admin/users/${userId}/survey-quality-review`, {
    method: "PATCH",
    json: { status, reason },
  });
}

export function getAdminExperiments() {
  return api<AdminExperiment[]>("/api/v1/admin/experiments");
}

export function patchExperiment(
  id: number,
  body: { title?: string; status?: string; rounds_per_scene?: number },
) {
  return api<AdminExperiment>(`/api/v1/admin/experiments/${id}`, {
    method: "PATCH",
    json: body,
  });
}

export function moveExperiment(id: number, direction: 1 | -1) {
  return api<{ ok: boolean }>(`/api/v1/admin/experiments/${id}/move?direction=${direction}`, {
    method: "POST",
  });
}

export function patchScene(
  id: number,
  body: {
    enabled?: boolean;
    required?: boolean;
    title?: string;
    short_desc?: string;
    option_a?: string;
    option_b?: string;
    option_a_text?: string;
    option_b_text?: string;
  },
) {
  return api<AdminScene>(`/api/v1/admin/scenes/${id}`, {
    method: "PATCH",
    json: body,
  });
}

export type AdminPage = {
  id: number;
  page_key: string;
  title: string;
  subtitle: string;
  status: string;
  audience: string;
  sort_order: number;
  updated_at?: string;
};

export type AdminContentBlock = {
  id: number;
  block_key: string;
  title: string;
  body: string;
  locale: string;
  version: number;
  updated_at?: string;
};

export function getAdminPages() {
  return api<AdminPage[]>("/api/v1/admin/pages");
}

export function patchAdminPage(
  id: number,
  body: { title?: string; subtitle?: string; status?: string; sort_order?: number },
) {
  return api<AdminPage>(`/api/v1/admin/pages/${id}`, { method: "PATCH", json: body });
}

export function getAdminContentBlocks() {
  return api<AdminContentBlock[]>("/api/v1/admin/content-blocks");
}

export function patchAdminContentBlock(id: number, body: { title?: string; body?: string }) {
  return api<AdminContentBlock>(`/api/v1/admin/content-blocks/${id}`, {
    method: "PATCH",
    json: body,
  });
}

export type AnnouncementKind = "notice" | "changelog";
export type AnnouncementStatus = "published" | "draft";

export type SiteAnnouncement = {
  id: number;
  kind: AnnouncementKind | string;
  title: string;
  body: string;
  pinned: boolean;
  published_at: string | null;
  updated_at: string | null;
};

export type AdminAnnouncement = SiteAnnouncement & {
  status: AnnouncementStatus | string;
  created_at: string | null;
};

export function getSiteAnnouncements(kind?: AnnouncementKind) {
  const q = kind ? `?kind=${kind}` : "";
  return api<SiteAnnouncement[]>(`/api/v1/site/announcements${q}`);
}

export function getAdminAnnouncements() {
  return api<AdminAnnouncement[]>("/api/v1/admin/announcements");
}

export function createAdminAnnouncement(body: {
  kind: AnnouncementKind;
  title: string;
  body?: string;
  status?: AnnouncementStatus;
  pinned?: boolean;
}) {
  return api<AdminAnnouncement>("/api/v1/admin/announcements", {
    method: "POST",
    json: body,
  });
}

export function patchAdminAnnouncement(
  id: number,
  body: {
    kind?: AnnouncementKind;
    title?: string;
    body?: string;
    status?: AnnouncementStatus;
    pinned?: boolean;
  },
) {
  return api<AdminAnnouncement>(`/api/v1/admin/announcements/${id}`, {
    method: "PATCH",
    json: body,
  });
}

export function deleteAdminAnnouncement(id: number) {
  return api<{ ok: boolean }>(`/api/v1/admin/announcements/${id}`, { method: "DELETE" });
}

export type SitePage = {
  page_key: string;
  title: string;
  subtitle: string;
  status: string;
  sort_order: number;
};

export type SiteContent = {
  block_key: string;
  title: string;
  body: string;
  version: number;
};

export function getSitePages() {
  return api<SitePage[]>("/api/v1/site/pages");
}

export function getSiteContent() {
  return api<SiteContent[]>("/api/v1/site/content");
}

export function getInviteCodes() {
  return api<InviteCode[]>("/api/v1/admin/invite-codes");
}

export function getSubAdmins() {
  return api<SubAdmin[]>("/api/v1/admin/sub-admins");
}

export function createInviteCode(body: {
  code: string;
  kind: "sub_admin" | "participant";
  max_uses: number;
  note: string;
  owner_id?: number | null;
}) {
  return api<InviteCode>("/api/v1/admin/invite-codes", { method: "POST", json: body });
}

export function assignInviteCode(id: number, owner_id: number | null) {
  return api<InviteCode>(`/api/v1/admin/invite-codes/${id}/assign`, {
    method: "PATCH",
    json: { owner_id },
  });
}

export function toggleInviteCode(id: number, enabled: boolean) {
  return api<{ ok: boolean }>(`/api/v1/admin/invite-codes/${id}?enabled=${enabled}`, {
    method: "PATCH",
  });
}

export function getAccountEvents() {
  return api<AccountEvent[]>("/api/v1/admin/account-events");
}

export async function downloadAdminCsv(
  kind: "users" | "surveys" | "rounds",
): Promise<void> {
  const token = localStorage.getItem("ym_token");
  const res = await fetch(`${API_BASE}/api/v1/admin/export/${kind}.csv`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename=\"?([^\";]+)\"?/);
  a.href = url;
  a.download = match?.[1] || `yangmind_${kind}.csv`;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

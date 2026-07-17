import { api, API_BASE } from "./client";

export type LeaderboardEntry = {
  rank: number;
  nickname: string;
  public_id: string;
  sessions_count: number;
  personality_summary: string;
  total_score: number;
};

export function getLeaderboard() {
  return api<{ period: string; items: LeaderboardEntry[] }>("/api/v1/leaderboard");
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
  total_score: number;
  sessions_count: number;
  personality_summary: string;
  survey_status: string;
  has_personality: boolean;
  status: string;
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
  max_uses: number;
  used_count: number;
  enabled: boolean;
  note: string;
  created_at?: string;
};

export type AccountEvent = {
  id: number;
  event_type: string;
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

export function createInviteCode(body: { code: string; max_uses: number; note: string }) {
  return api<InviteCode>("/api/v1/admin/invite-codes", { method: "POST", json: body });
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
  a.click();
  URL.revokeObjectURL(url);
}

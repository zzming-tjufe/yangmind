import { api } from "./client";

export type User = {
  id: number;
  public_id: string;
  email: string;
  nickname: string;
  role: string;
  status: string;
  is_debug?: boolean;
  is_sudo?: boolean;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export function register(body: {
  email: string;
  password: string;
  nickname: string;
  invite_code: string;
}) {
  return api<TokenResponse>("/api/v1/auth/register", { method: "POST", json: body });
}

export function login(body: { email: string; password: string }) {
  return api<TokenResponse>("/api/v1/auth/login", { method: "POST", json: body });
}

export function me() {
  return api<User>("/api/v1/auth/me");
}

export function changePassword(body: { current_password: string; new_password: string }) {
  return api<{ ok: boolean }>("/api/v1/auth/change-password", {
    method: "POST",
    json: body,
  });
}

/** 仅 sudo：清空本人问卷 / 理解检查 / 对局进度 */
export function sudoResetProgress() {
  return api<{ ok: boolean; deleted: Record<string, number> }>(
    "/api/v1/auth/sudo-reset-progress",
    { method: "POST" },
  );
}

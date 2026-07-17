import { api } from "./client";

export type User = {
  id: number;
  public_id: string;
  email: string;
  nickname: string;
  role: string;
  status: string;
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
  invite_code?: string;
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

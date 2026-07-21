// 空字符串 = 同域（经 Nginx 反代 /api）；未设置时本地默认直连 8003
const API_BASE =
  import.meta.env.VITE_API_BASE !== undefined
    ? String(import.meta.env.VITE_API_BASE).replace(/\/$/, "")
    : "http://127.0.0.1:8003";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type ValidationError = {
  loc?: Array<string | number>;
  msg?: string;
  type?: string;
};

const fieldNames: Record<string, string> = {
  email: "邮箱",
  password: "密码",
  nickname: "昵称",
  invite_code: "邀请码",
};

function validationMessage(error: ValidationError): string {
  const field = error.loc?.at(-1);
  const fieldName =
    typeof field === "string" ? fieldNames[field] || field : "提交内容";
  const type = error.type || "";

  if (field === "email" || type.includes("email")) {
    return "邮箱格式不正确，请输入类似 name@example.com 的地址";
  }
  if (type === "missing") return `请输入${fieldName}`;
  if (type.includes("too_short") || type.includes("min_length")) {
    return field === "password" ? "密码至少需要 6 个字符" : `${fieldName}内容太短`;
  }
  if (type.includes("too_long") || type.includes("max_length")) {
    return `${fieldName}内容太长`;
  }
  return error.msg ? `${fieldName}：${error.msg}` : `${fieldName}填写不正确`;
}

function errorMessage(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object" || !("detail" in data)) return fallback;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return (
      detail
        .filter((item): item is ValidationError => Boolean(item && typeof item === "object"))
        .map(validationMessage)
        .join("；") || fallback
    );
  }
  return fallback;
}

function getToken(): string | null {
  return localStorage.getItem("ym_token");
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem("ym_token", token);
  else localStorage.removeItem("ym_token");
}

function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError || (e instanceof Error && e.name === "ApiError");
}

export async function api<T>(
  path: string,
  options: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const url = `${API_BASE}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...options,
      headers,
      body: options.json !== undefined ? JSON.stringify(options.json) : options.body,
    });
  } catch {
    const hint = API_BASE
      ? `无法连接 API（${API_BASE}），请检查网络或稍后重试`
      : "无法连接服务器，请稍后重试";
    throw new ApiError(0, hint);
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = errorMessage(data, detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export { API_BASE, isApiError };

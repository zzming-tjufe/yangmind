import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { getPublicAppVersion } from "../api/admin";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

function errorText(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error && e.name === "ApiError") return e.message;
  if (e instanceof Error && e.message) return e.message;
  return "无法连接服务器，请稍后重试";
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function AuthPage() {
  const { login, register } = useAuth();
  const { toast } = useToast();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [flipping, setFlipping] = useState(false);
  const [appVersion, setAppVersion] = useState("v0.4.1");

  useEffect(() => {
    let cancelled = false;
    getPublicAppVersion()
      .then((v) => {
        if (!cancelled) setAppVersion(v);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  function switchMode(next: "login" | "register") {
    if (next === mode || flipping) return;
    setFlipping(true);
    setMode(next);
    window.setTimeout(() => setFlipping(false), 650);
  }

  async function submit(nextMode: "login" | "register") {
    const account = email.trim();
    if (!account) {
      toast(nextMode === "login" ? "请输入昵称或邮箱" : "请输入邮箱");
      return;
    }
    if (nextMode === "register" && !EMAIL_PATTERN.test(account)) {
      toast("邮箱格式不正确，请输入类似 name@example.com 的地址");
      return;
    }
    if (!password) {
      toast("请输入密码");
      return;
    }
    if (password.length < 6) {
      toast("密码至少需要 6 个字符");
      return;
    }
    if (nextMode === "register" && !nickname.trim()) {
      toast("请输入昵称");
      return;
    }
    if (nextMode === "register" && !inviteCode.trim()) {
      toast("请填写邀请码");
      return;
    }
    setBusy(true);
    try {
      if (nextMode === "login") await login(account, password);
      else await register(account, password, nickname.trim(), inviteCode.trim());
      toast(nextMode === "login" ? "登录成功" : "注册成功");
    } catch (e) {
      toast(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  const passwordType = showPassword ? "text" : "password";

  return (
    <section id="auth">
      <div className="auth-visual">
        <div className="auth-ambient" aria-hidden>
          <i />
          <i />
        </div>
        <div className="auth-float-words" aria-hidden>
          <span className="auth-reveal" style={{ ["--d" as string]: "200ms" }}>
            合作
          </span>
          <span className="auth-reveal" style={{ ["--d" as string]: "480ms" }}>
            信任
          </span>
          <span className="auth-reveal" style={{ ["--d" as string]: "760ms" }}>
            人格
          </span>
        </div>
        <div className="brand auth-reveal" style={{ ["--d" as string]: "80ms" }}>
          <i>YM</i>
          <strong>YangMind Lab</strong>
        </div>
        <div className="copy">
          <div className="eyebrow auth-reveal" style={{ ["--d" as string]: "320ms" }}>
            行为科学实验平台
          </div>
          <h1 className="auth-reveal" style={{ ["--d" as string]: "560ms" }}>
            在选择之间，
            <br />
            看见合作的可能。
          </h1>
          <p className="auth-reveal" style={{ ["--d" as string]: "880ms" }}>
            连接人格测量与策略博弈，让每一次决策都成为理解合作行为的线索。
          </p>
          
        </div>
        <div className="copyright auth-reveal" style={{ ["--d" as string]: "1180ms" }}>
          © 2026 YangMind Lab · {appVersion}
        </div>
      </div>
      <div className="auth-panel">
        <div className="auth-flip-scene">
          <div className={`auth-flip-card${mode === "register" ? " is-flipped" : ""}`}>
            {/* 正面：登录 */}
            <div className="auth-card auth-face auth-face-front">
              <div className="eyebrow">欢迎来到 YANGMIND LAB</div>
              <h2>登录你的账号</h2>
              <p>继续你的问卷与博弈实验</p>
              <div className="tabs" role="tablist">
                <button type="button" className="active" role="tab" aria-selected>
                  登录
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={false}
                  disabled={flipping}
                  onClick={() => switchMode("register")}
                >
                  注册
                </button>
              </div>
              <label className="field">
                昵称 / 邮箱
                <input
                  type="text"
                  placeholder="昵称或注册邮箱"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="username"
                />
              </label>
              <label className="field">
                密码
                <span className="password-field">
                  <input
                    type={passwordType}
                    placeholder="请输入密码"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") submit("login");
                    }}
                  />
                  <button
                    type="button"
                    className="password-toggle"
                    aria-label={showPassword ? "隐藏密码" : "显示密码"}
                    onClick={() => setShowPassword((v) => !v)}
                  >
                    {showPassword ? "隐藏" : "显示"}
                  </button>
                </span>
              </label>
              <button
                className="primary auth-submit"
                onClick={() => submit("login")}
                disabled={busy || flipping}
                type="button"
              >
                {busy && mode === "login" ? "请稍候…" : "登录并进入 →"}
              </button>
            </div>

            {/* 背面：注册 */}
            <div className="auth-card auth-face auth-face-back">
              <div className="eyebrow">欢迎来到 YANGMIND LAB</div>
              <h2>创建研究账号</h2>
              <p>注册后即可开始人格问卷与合作博弈</p>
              <div className="tabs" role="tablist">
                <button
                  type="button"
                  role="tab"
                  aria-selected={false}
                  disabled={flipping}
                  onClick={() => switchMode("login")}
                >
                  登录
                </button>
                <button type="button" className="active" role="tab" aria-selected>
                  注册
                </button>
              </div>
              <label className="field">
                昵称
                <input
                  placeholder="唯一昵称，可用于登录"
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  autoComplete="nickname"
                />
              </label>
              <label className="field">
                邮箱
                <input
                  type="email"
                  placeholder="请输入邮箱"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="username"
                />
              </label>
              <label className="field">
                密码
                <span className="password-field">
                  <input
                    type={passwordType}
                    placeholder="请输入密码"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="new-password"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") submit("register");
                    }}
                  />
                  <button
                    type="button"
                    className="password-toggle"
                    aria-label={showPassword ? "隐藏密码" : "显示密码"}
                    onClick={() => setShowPassword((v) => !v)}
                  >
                    {showPassword ? "隐藏" : "显示"}
                  </button>
                </span>
              </label>
              <label className="field">
                邀请码（必填）
                <input
                  placeholder="请向管理员索取邀请码"
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value)}
                  required
                  onKeyDown={(e) => {
                    if (e.key === "Enter") submit("register");
                  }}
                />
              </label>
              <button
                className="primary auth-submit"
                onClick={() => submit("register")}
                disabled={busy || flipping}
                type="button"
              >
                {busy && mode === "register" ? "请稍候…" : "注册并进入 →"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

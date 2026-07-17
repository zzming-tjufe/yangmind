import { useState } from "react";
import { ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

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

  function switchMode(next: "login" | "register") {
    if (next === mode || flipping) return;
    setFlipping(true);
    setMode(next);
    window.setTimeout(() => setFlipping(false), 650);
  }

  async function submit(nextMode: "login" | "register") {
    if (!email.trim()) {
      toast("请输入邮箱");
      return;
    }
    if (!password) {
      toast("请输入密码");
      return;
    }
    if (nextMode === "register" && !nickname.trim()) {
      toast("请输入昵称");
      return;
    }
    setBusy(true);
    try {
      if (nextMode === "login") await login(email.trim(), password);
      else await register(email.trim(), password, nickname.trim(), inviteCode.trim() || undefined);
      toast(nextMode === "login" ? "登录成功" : "注册成功");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "请求失败");
    } finally {
      setBusy(false);
    }
  }

  const passwordType = showPassword ? "text" : "password";

  return (
    <section id="auth">
      <div className="auth-visual">
        <div className="brand">
          <i>YM</i>
          <strong>YangMind Lab</strong>
        </div>
        <div className="copy">
          <div className="eyebrow">行为科学实验平台</div>
          <h1>
            在选择之间，
            <br />
            看见合作的可能。
          </h1>
          <p>连接人格测量与策略博弈，让每一次决策都成为理解合作行为的线索。</p>
        </div>
        <div className="copyright">© 2026 YangMind Lab · 行为与人格研究中心</div>
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
                    autoComplete="current-password"
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
                  placeholder="你希望如何被称呼"
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
                邀请码（可选）
                <input
                  placeholder="如有邀请码请填写"
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value)}
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

import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import {
  downloadAdminCsv,
  getAdminPersonality,
  getAdminStats,
  getAdminUsers,
  resetUserPassword,
  setUserStatus,
  type AdminPersonality,
  type AdminStats,
  type AdminUser,
} from "../api/admin";
import { useToast } from "../context/ToastContext";

export function AdminUsersPage() {
  const { toast } = useToast();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [q, setQ] = useState("");
  const [profile, setProfile] = useState<AdminPersonality | null>(null);
  const [busy, setBusy] = useState(false);

  async function load(search?: string) {
    const [s, u] = await Promise.all([getAdminStats(), getAdminUsers(search)]);
    setStats(s);
    setUsers(u.items);
  }

  useEffect(() => {
    load().catch((e) => toast(e instanceof ApiError ? e.message : "加载失败"));
  }, [toast]);

  async function openProfile(u: AdminUser) {
    if (!u.has_personality) {
      toast("该用户尚未完成问卷，暂时没有人格画像");
      return;
    }
    try {
      setProfile(await getAdminPersonality(u.id));
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "加载画像失败");
    }
  }

  async function toggleStatus(u: AdminUser) {
    const next = u.status === "active" ? "disabled" : "active";
    setBusy(true);
    try {
      await setUserStatus(u.id, next);
      toast(next === "active" ? "已启用账号" : "已禁用账号");
      await load(q || undefined);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  async function onResetPassword(u: AdminUser) {
    const pwd = window.prompt(`为 ${u.nickname} 设置新密码（至少 6 位）`);
    if (!pwd) return;
    if (pwd.length < 6) {
      toast("密码至少 6 位");
      return;
    }
    setBusy(true);
    try {
      await resetUserPassword(u.id, pwd);
      toast("密码已重置");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "重置失败");
    } finally {
      setBusy(false);
    }
  }

  async function onExport(kind: "users" | "surveys" | "rounds") {
    try {
      await downloadAdminCsv(kind);
      toast("导出已开始下载");
    } catch (e) {
      toast(e instanceof Error ? e.message : "导出失败");
    }
  }

  return (
    <div className="page">
      <div className="statgrid admin-stats">
        {[
          ["总注册用户", stats ? String(stats.total_users) : "-", ""],
          ["问卷完成率", stats ? `${stats.survey_completion_rate}%` : "-", ""],
          ["有效博弈轮次", stats ? String(stats.valid_rounds) : "-", ""],
          ["平均合作率", stats ? `${stats.avg_coop_rate}%` : "-", ""],
        ].map(([a, b, c]) => (
          <div className="stat card" key={a}>
            <span>{a}</span>
            <b>{b}</b>
            <em>{c || " "}</em>
          </div>
        ))}
      </div>

      <div className="export-bar card">
        <div>
          <b>研究数据导出</b>
          <small>下载 CSV，可用 Excel 打开</small>
        </div>
        <div className="export-actions">
          <button className="secondary" type="button" onClick={() => onExport("users")}>
            导出用户
          </button>
          <button className="secondary" type="button" onClick={() => onExport("surveys")}>
            导出问卷
          </button>
          <button className="secondary" type="button" onClick={() => onExport("rounds")}>
            导出对局轮次
          </button>
        </div>
      </div>

      <section className="table card user-table">
        <div className="tablehead">
          <h3>用户与人格结果</h3>
          <input
            className="search"
            placeholder="搜索姓名 / ID / 邮箱"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") load(q).catch(() => undefined);
            }}
          />
        </div>
        <div className="row header admin-user-head">
          <span>用户</span>
          <span>总得分</span>
          <span>场次</span>
          <span>人格摘要</span>
          <span>问卷</span>
          <span>状态</span>
          <span>操作</span>
        </div>
        {users.map((u) => (
          <div className="row admin-user-row" key={u.id}>
            <span className="user">
              <i>{u.nickname.slice(0, 1)}</i>
              <b>
                {u.nickname}
                <small style={{ display: "block", color: "#999" }}>
                  {u.public_id} · {u.email}
                </small>
              </b>
            </span>
            <b>{u.total_score}</b>
            <span>{u.sessions_count}</span>
            <span>{u.personality_summary}</span>
            <span className={`badge ${u.survey_status === "已完成" ? "" : "warn"}`}>
              {u.survey_status}
            </span>
            <span className={`badge ${u.status === "active" ? "" : "warn"}`}>
              {u.status === "active" ? "正常" : "已禁用"}
            </span>
            <div className="admin-row-actions">
              <button
                className="secondary"
                type="button"
                disabled={!u.has_personality}
                onClick={() => openProfile(u)}
              >
                画像
              </button>
              <button className="secondary" type="button" disabled={busy} onClick={() => toggleStatus(u)}>
                {u.status === "active" ? "禁用" : "启用"}
              </button>
              <button className="secondary" type="button" disabled={busy} onClick={() => onResetPassword(u)}>
                重置密码
              </button>
            </div>
          </div>
        ))}
      </section>

      {profile && (
        <div className="profile-overlay" onClick={() => setProfile(null)}>
          <section className="profile-modal" role="dialog" onClick={(e) => e.stopPropagation()}>
            <header className="profile-modal-head">
              <div className="profile-person">
                <i>{profile.nickname.slice(0, 1)}</i>
                <div>
                  <b>
                    {profile.nickname} · 人格详细档案
                  </b>
                  <small>
                    {profile.public_id} · {profile.summary_label}
                  </small>
                </div>
              </div>
              <button type="button" onClick={() => setProfile(null)} aria-label="关闭">
                ×
              </button>
            </header>
            <div className="profile-modal-body">
              <div className="personality-scores">
                {profile.dimensions.map((d) => (
                  <article className="score-card" key={d.code}>
                    <div className="score-title">
                      <i>{d.code}</i>
                      <div>
                        <b>{d.name}</b>
                        <small>{d.english}</small>
                      </div>
                      <strong>
                        {d.score.toFixed(1)} / 5.0
                      </strong>
                    </div>
                    <div className="score-track">
                      <i style={{ width: `${(d.score / 5) * 100}%` }} />
                    </div>
                    <p>{d.band_text}</p>
                  </article>
                ))}
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

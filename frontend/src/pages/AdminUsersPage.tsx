import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import {
  allowSurveyRetake,
  downloadAdminCsv,
  getAdminPersonality,
  getAdminStats,
  getAdminUsers,
  getSurveyQualityReview,
  resetUserPassword,
  reviewSurveyQuality,
  setUserStatus,
  type AdminPersonality,
  type AdminStats,
  type AdminUser,
  type SurveyQualityReview,
} from "../api/admin";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { isSuperAdmin } from "../lib/roles";

export function AdminUsersPage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const superAdmin = isSuperAdmin(user?.role);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [q, setQ] = useState("");
  const [profile, setProfile] = useState<AdminPersonality | null>(null);
  const [qualityReview, setQualityReview] = useState<SurveyQualityReview | null>(null);
  const [qualityReviewUser, setQualityReviewUser] = useState<AdminUser | null>(null);
  const [reviewReason, setReviewReason] = useState("");
  const [busy, setBusy] = useState(false);

  async function load(search?: string) {
    const u = await getAdminUsers(search);
    setUsers(u.items);
    if (superAdmin) {
      setStats(await getAdminStats());
    } else {
      setStats(null);
    }
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

  async function onAllowRetake(u: AdminUser) {
    const confirmed = window.confirm(
      `确定授权「${u.nickname}」重新作答人格问卷吗？\n\n原正式答卷会留档，新答卷将成为后续分析使用的答卷。`,
    );
    if (!confirmed) return;
    setBusy(true);
    try {
      const result = await allowSurveyRetake(u.id);
      toast(`已授权重做（第 ${result.retake_count} 次），原答卷已归档`);
      setProfile(null);
      await load(q || undefined);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "授权失败");
    } finally {
      setBusy(false);
    }
  }

  async function openQualityReview(u: AdminUser) {
    try {
      const review = await getSurveyQualityReview(u.id);
      setQualityReviewUser(u);
      setQualityReview(review);
      setReviewReason(review.review_reason || "");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "加载质量信息失败");
    }
  }

  async function submitQualityReview(status: "kept" | "excluded") {
    if (!qualityReviewUser) return;
    if (reviewReason.trim().length < 2) {
      toast("请填写至少 2 个字的复核理由");
      return;
    }
    setBusy(true);
    try {
      const review = await reviewSurveyQuality(
        qualityReviewUser.id,
        status,
        reviewReason.trim(),
      );
      setQualityReview(review);
      toast(status === "kept" ? "已复核为保留答卷" : "已复核为排除答卷");
      await load(q || undefined);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "复核失败");
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
      {superAdmin ? (
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
      ) : (
        <p style={{ marginBottom: 16, color: "#666" }}>
          你只能查看和管理通过你名下邀请码注册的员工。
        </p>
      )}

      {superAdmin ? (
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
      ) : null}

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
            <span
              className={`badge ${
                u.quality_passed === false || u.survey_status === "质量未过"
                  ? "danger"
                  : u.survey_status === "已完成"
                    ? ""
                    : "warn"
              }`}
              title={
                u.quality_passed === false
                  ? "该用户问卷未通过质量检查（可能未认真作答）"
                  : undefined
              }
            >
              {u.quality_passed === false || u.survey_status === "质量未过"
                ? "质量未过"
                : u.survey_status}
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
              <button
                className="secondary"
                type="button"
                disabled={busy || !u.can_retake_survey}
                title={u.retake_block_reason || "原答卷会留档，授权后用户可重新作答一次"}
                onClick={() => onAllowRetake(u)}
              >
                授权重做{u.retake_count ? `（${u.retake_count}）` : ""}
              </button>
              <button
                className="secondary"
                type="button"
                disabled={busy || !u.has_submitted_survey}
                onClick={() => openQualityReview(u)}
              >
                质量复核
                {u.quality_review_status === "pending" ? " · 待处理" : ""}
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
              {profile.quality_passed === false ? (
                <div className="quality-fail-banner" role="alert">
                  <b>质量检测未通过</b>
                  <span>该用户问卷可能未认真作答，人格结果仅供参考，且未解锁博弈实验。</span>
                </div>
              ) : null}
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

      {qualityReview && qualityReviewUser && (
        <div className="profile-overlay" onClick={() => setQualityReview(null)}>
          <section className="profile-modal" role="dialog" onClick={(e) => e.stopPropagation()}>
            <header className="profile-modal-head">
              <div className="profile-person">
                <i>{qualityReviewUser.nickname.slice(0, 1)}</i>
                <div>
                  <b>{qualityReviewUser.nickname} · 问卷质量复核</b>
                  <small>答卷 #{qualityReview.response_id} · {qualityReview.review_status}</small>
                </div>
              </div>
              <button type="button" onClick={() => setQualityReview(null)} aria-label="关闭">×</button>
            </header>
            <div className="profile-modal-body">
              <div className="quality-fail-banner" role="status">
                <b>{qualityReview.hard_exclusion ? "存在硬性排除原因" : "质量信号汇总"}</b>
                <span>
                  软标记：{qualityReview.soft_flags.join("、") || "无"}；失焦次数：
                  {qualityReview.blur_count}
                </span>
              </div>
              <div className="personality-scores">
                <article className="score-card">
                  <div className="score-title"><b>注意力题原始选择</b></div>
                  <p>{JSON.stringify(qualityReview.attention_answers)}</p>
                </article>
                <article className="score-card">
                  <div className="score-title"><b>自报认真程度</b></div>
                  <p>{JSON.stringify(qualityReview.diligence_answers)}</p>
                </article>
                <article className="score-card">
                  <div className="score-title"><b>各组作答时间（秒）</b></div>
                  <p>{JSON.stringify(qualityReview.page_timings_seconds)}</p>
                </article>
              </div>
              <label className="field" style={{ marginTop: 16 }}>
                复核理由
                <textarea
                  rows={3}
                  value={reviewReason}
                  onChange={(event) => setReviewReason(event.target.value)}
                  placeholder="例如：注意力题正确、总时长正常，保留答卷"
                />
              </label>
              <div className="export-actions" style={{ marginTop: 14 }}>
                <button className="primary" type="button" disabled={busy} onClick={() => submitQualityReview("kept")}>保留答卷</button>
                <button className="secondary" type="button" disabled={busy} onClick={() => submitQualityReview("excluded")}>排除答卷</button>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

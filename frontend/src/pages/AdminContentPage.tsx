import { useEffect, useMemo, useState } from "react";
import { ApiError } from "../api/client";
import {
  createAdminAnnouncement,
  deleteAdminAnnouncement,
  getAdminAnnouncements,
  getAdminContentBlocks,
  getAdminExperiments,
  patchAdminAnnouncement,
  patchAdminContentBlock,
  patchScene,
  type AdminAnnouncement,
  type AdminContentBlock,
  type AdminScene,
  type AnnouncementKind,
  type AnnouncementStatus,
} from "../api/admin";
import { AdminListStatus } from "../components/AdminListStatus";
import { ModalOverlay } from "../components/ModalPortal";
import { useToast } from "../context/ToastContext";

type Tab = "announcements" | "blocks" | "scenes";

const BLOCK_LABELS: Record<string, string> = {
  "bfi.intro": "BFI 理论导读",
  "bfi.survey_hero": "BFI 作答页导语",
  "games.lobby": "博弈大厅",
  "rank.hero": "排行榜导语",
  "announcement.banner": "平台公告横幅",
};

const KIND_LABEL: Record<string, string> = {
  notice: "测试通告",
  changelog: "更新日志",
};

const emptyAnnForm = {
  kind: "notice" as AnnouncementKind,
  title: "",
  body: "",
  status: "draft" as AnnouncementStatus,
  pinned: false,
};

export function AdminContentPage() {
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>("announcements");
  const [blocks, setBlocks] = useState<AdminContentBlock[]>([]);
  const [scenes, setScenes] = useState<AdminScene[]>([]);
  const [announcements, setAnnouncements] = useState<AdminAnnouncement[]>([]);
  const [editBlock, setEditBlock] = useState<AdminContentBlock | null>(null);
  const [editScene, setEditScene] = useState<AdminScene | null>(null);
  const [editAnn, setEditAnn] = useState<AdminAnnouncement | null>(null);
  const [creatingAnn, setCreatingAnn] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [annForm, setAnnForm] = useState(emptyAnnForm);
  const [sceneForm, setSceneForm] = useState({
    title: "",
    short_desc: "",
    option_a: "",
    option_b: "",
    option_a_text: "",
    option_b_text: "",
  });
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const [b, exps, anns] = await Promise.all([
        getAdminContentBlocks(),
        getAdminExperiments(),
        getAdminAnnouncements(),
      ]);
      setBlocks(b);
      setScenes(exps.flatMap((e) => e.scenes));
      setAnnouncements(anns);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load().catch((e) => {
      setLoading(false);
      toast(e instanceof ApiError ? e.message : "加载失败");
    });
  }, [toast]);

  const sortedBlocks = useMemo(
    () => [...blocks].sort((a, b) => a.block_key.localeCompare(b.block_key)),
    [blocks],
  );

  function openBlock(b: AdminContentBlock) {
    setEditBlock(b);
    setTitle(b.title);
    setBody(b.body);
  }

  function openScene(s: AdminScene) {
    setEditScene(s);
    setSceneForm({
      title: s.title,
      short_desc: s.short_desc,
      option_a: s.option_a,
      option_b: s.option_b,
      option_a_text: s.option_a_text,
      option_b_text: s.option_b_text,
    });
  }

  function openCreateAnn() {
    setEditAnn(null);
    setAnnForm(emptyAnnForm);
    setCreatingAnn(true);
  }

  function openEditAnn(a: AdminAnnouncement) {
    setCreatingAnn(false);
    setEditAnn(a);
    setAnnForm({
      kind: (a.kind === "changelog" ? "changelog" : "notice") as AnnouncementKind,
      title: a.title,
      body: a.body,
      status: (a.status === "published" ? "published" : "draft") as AnnouncementStatus,
      pinned: a.pinned,
    });
  }

  function closeAnnModal() {
    setCreatingAnn(false);
    setEditAnn(null);
  }

  async function saveBlock() {
    if (!editBlock) return;
    setBusy(true);
    try {
      await patchAdminContentBlock(editBlock.id, { title, body });
      setEditBlock(null);
      await load();
      toast("内容已保存");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveScene() {
    if (!editScene) return;
    setBusy(true);
    try {
      await patchScene(editScene.id, sceneForm);
      setEditScene(null);
      await load();
      toast("场景文案已保存");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveAnn() {
    if (!annForm.title.trim()) {
      toast("请填写标题");
      return;
    }
    setBusy(true);
    try {
      if (creatingAnn) {
        await createAdminAnnouncement({
          kind: annForm.kind,
          title: annForm.title.trim(),
          body: annForm.body,
          status: annForm.status,
          pinned: annForm.pinned,
        });
        toast("公告已创建");
      } else if (editAnn) {
        await patchAdminAnnouncement(editAnn.id, {
          kind: annForm.kind,
          title: annForm.title.trim(),
          body: annForm.body,
          status: annForm.status,
          pinned: annForm.pinned,
        });
        toast("公告已保存");
      }
      closeAnnModal();
      await load();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function removeAnn(a: AdminAnnouncement) {
    if (!window.confirm(`确认删除「${a.title}」？`)) return;
    setBusy(true);
    try {
      await deleteAdminAnnouncement(a.id);
      await load();
      toast("已删除");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "删除失败");
    } finally {
      setBusy(false);
    }
  }

  const annModalOpen = creatingAnn || editAnn != null;

  return (
    <div className="page">
      <section className="hero card">
        <div>
          <div className="eyebrow">CONTENT CMS</div>
          <h2>内容管理</h2>
          <p>发布测试通告与更新日志，并编辑问卷说明、大厅文案与博弈场景文案。</p>
        </div>
      </section>

      <div className="cms-tabs">
        <button
          type="button"
          className={tab === "announcements" ? "active" : ""}
          onClick={() => setTab("announcements")}
        >
          公告栏
        </button>
        <button
          type="button"
          className={tab === "blocks" ? "active" : ""}
          onClick={() => setTab("blocks")}
        >
          平台文案
        </button>
        <button
          type="button"
          className={tab === "scenes" ? "active" : ""}
          onClick={() => setTab("scenes")}
        >
          场景文案
        </button>
      </div>

      {tab === "announcements" && (
        <section className="card">
          <div className="tablehead">
            <h3>测试通告 / 更新日志</h3>
            <button className="primary" type="button" onClick={openCreateAnn}>
              新建公告
            </button>
          </div>
          <div className="manage-list">
            {loading ? (
              <AdminListStatus loading />
            ) : (
              <>
                {announcements.map((a) => (
                  <div className="manage-item" key={a.id}>
                    <i>{a.kind === "changelog" ? "↺" : "!"}</i>
                    <div>
                      <b>
                        {a.pinned ? "[置顶] " : ""}
                        {a.title}
                      </b>
                      <small>
                        {KIND_LABEL[a.kind] || a.kind} ·{" "}
                        {a.status === "published" ? "已发布" : "草稿"}
                        {a.published_at
                          ? ` · ${new Date(a.published_at).toLocaleString("zh-CN")}`
                          : ""}
                      </small>
                    </div>
                    <span className={`badge ${a.status === "published" ? "" : "warn"}`}>
                      {a.status === "published" ? "已发布" : "草稿"}
                    </span>
                    <div className="actions">
                      <button type="button" onClick={() => openEditAnn(a)}>
                        编辑
                      </button>
                      <button type="button" disabled={busy} onClick={() => removeAnn(a)}>
                        删除
                      </button>
                    </div>
                  </div>
                ))}
                {announcements.length === 0 && (
                  <AdminListStatus empty emptyText="暂无公告，点击右上角新建" />
                )}
              </>
            )}
          </div>
        </section>
      )}

      {tab === "blocks" && (
        <section className="card">
          <div className="tablehead">
            <h3>内容块</h3>
            <span style={{ fontSize: 12, color: "#999" }}>
              横幅公告与页面固定文案；修改后参与端立即生效
            </span>
          </div>
          <div className="manage-list">
            {loading ? (
              <AdminListStatus loading />
            ) : sortedBlocks.length === 0 ? (
              <AdminListStatus empty emptyText="暂无内容块" />
            ) : (
              sortedBlocks.map((b) => (
                <div className="manage-item" key={b.id}>
                  <i>✦</i>
                  <div>
                    <b>{BLOCK_LABELS[b.block_key] || b.block_key}</b>
                    <small>
                      {b.block_key} · v{b.version} · {b.title || "无标题"}
                    </small>
                  </div>
                  <span className="badge">{b.body.trim() ? "有内容" : "空"}</span>
                  <div className="actions">
                    <button type="button" onClick={() => openBlock(b)}>
                      编辑
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      )}

      {tab === "scenes" && (
        <section className="card">
          <div className="tablehead">
            <h3>实验场景</h3>
          </div>
          <div className="manage-list">
            {loading ? (
              <AdminListStatus loading />
            ) : scenes.length === 0 ? (
              <AdminListStatus empty emptyText="暂无场景" />
            ) : (
              scenes.map((s) => (
                <div className="manage-item" key={s.id}>
                  <i>{s.no}</i>
                  <div>
                    <b>{s.title}</b>
                    <small>
                      {s.scene_key} · {s.short_desc.slice(0, 48)}
                      {s.short_desc.length > 48 ? "…" : ""}
                    </small>
                  </div>
                  <span className={`badge ${s.enabled ? "" : "warn"}`}>
                    {s.enabled ? "启用" : "停用"}
                  </span>
                  <div className="actions">
                    <button type="button" onClick={() => openScene(s)}>
                      编辑文案
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      )}

      {annModalOpen && (
        <ModalOverlay onClose={closeAnnModal}>
          <div className="profile-modal cms-modal" onClick={(e) => e.stopPropagation()}>
            <div className="profile-modal-head">
              <div className="profile-person">
                <i>!</i>
                <div>
                  <b>{creatingAnn ? "新建公告" : "编辑公告"}</b>
                  <small>测试通告或更新日志</small>
                </div>
              </div>
              <button type="button" onClick={closeAnnModal}>
                ×
              </button>
            </div>
            <div className="cms-form">
              <label className="field">
                类型
                <select
                  value={annForm.kind}
                  onChange={(e) =>
                    setAnnForm((f) => ({
                      ...f,
                      kind: e.target.value as AnnouncementKind,
                    }))
                  }
                >
                  <option value="notice">测试通告</option>
                  <option value="changelog">更新日志</option>
                </select>
              </label>
              <label className="field">
                标题
                <input
                  value={annForm.title}
                  onChange={(e) => setAnnForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder="例如：本周测试安排 / v0.2 更新说明"
                />
              </label>
              <label className="field">
                正文
                <textarea
                  rows={8}
                  value={annForm.body}
                  onChange={(e) => setAnnForm((f) => ({ ...f, body: e.target.value }))}
                  placeholder="支持 Markdown。可用标题、列表、加粗等，例如：## 更新要点"
                />
              </label>
              <label className="field">
                状态
                <select
                  value={annForm.status}
                  onChange={(e) =>
                    setAnnForm((f) => ({
                      ...f,
                      status: e.target.value as AnnouncementStatus,
                    }))
                  }
                >
                  <option value="draft">草稿（仅管理可见）</option>
                  <option value="published">发布（参与端可见）</option>
                </select>
              </label>
              <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                <input
                  type="checkbox"
                  checked={annForm.pinned}
                  onChange={(e) => setAnnForm((f) => ({ ...f, pinned: e.target.checked }))}
                />
                置顶显示
              </label>
              <div className="cms-form-actions">
                <button className="secondary" type="button" onClick={closeAnnModal}>
                  取消
                </button>
                <button className="primary" type="button" disabled={busy} onClick={saveAnn}>
                  {busy ? "保存中…" : "保存"}
                </button>
              </div>
            </div>
          </div>
        </ModalOverlay>
      )}

      {editBlock && (
        <ModalOverlay onClose={() => setEditBlock(null)}>
          <div className="profile-modal cms-modal" onClick={(e) => e.stopPropagation()}>
            <div className="profile-modal-head">
              <div className="profile-person">
                <i>✦</i>
                <div>
                  <b>{BLOCK_LABELS[editBlock.block_key] || editBlock.block_key}</b>
                  <small>{editBlock.block_key}</small>
                </div>
              </div>
              <button type="button" onClick={() => setEditBlock(null)}>
                ×
              </button>
            </div>
            <div className="cms-form">
              <label className="field">
                标题
                <input value={title} onChange={(e) => setTitle(e.target.value)} />
              </label>
              <label className="field">
                正文
                <textarea
                  rows={8}
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  placeholder="支持多行。公告留空则不展示横幅。"
                />
              </label>
              <div className="cms-form-actions">
                <button className="secondary" type="button" onClick={() => setEditBlock(null)}>
                  取消
                </button>
                <button className="primary" type="button" disabled={busy} onClick={saveBlock}>
                  保存
                </button>
              </div>
            </div>
          </div>
        </ModalOverlay>
      )}

      {editScene && (
        <ModalOverlay onClose={() => setEditScene(null)}>
          <div className="profile-modal cms-modal" onClick={(e) => e.stopPropagation()}>
            <div className="profile-modal-head">
              <div className="profile-person">
                <i>{editScene.no}</i>
                <div>
                  <b>场景文案</b>
                  <small>{editScene.scene_key}</small>
                </div>
              </div>
              <button type="button" onClick={() => setEditScene(null)}>
                ×
              </button>
            </div>
            <div className="cms-form">
              <label className="field">
                标题
                <input
                  value={sceneForm.title}
                  onChange={(e) => setSceneForm((f) => ({ ...f, title: e.target.value }))}
                />
              </label>
              <label className="field">
                简介
                <textarea
                  rows={3}
                  value={sceneForm.short_desc}
                  onChange={(e) => setSceneForm((f) => ({ ...f, short_desc: e.target.value }))}
                />
              </label>
              <div className="cms-option-grid">
                <label className="field">
                  选项 A 名称
                  <input
                    value={sceneForm.option_a}
                    onChange={(e) => setSceneForm((f) => ({ ...f, option_a: e.target.value }))}
                  />
                </label>
                <label className="field">
                  选项 B 名称
                  <input
                    value={sceneForm.option_b}
                    onChange={(e) => setSceneForm((f) => ({ ...f, option_b: e.target.value }))}
                  />
                </label>
              </div>
              <label className="field">
                选项 A 说明
                <textarea
                  rows={3}
                  value={sceneForm.option_a_text}
                  onChange={(e) => setSceneForm((f) => ({ ...f, option_a_text: e.target.value }))}
                />
              </label>
              <label className="field">
                选项 B 说明
                <textarea
                  rows={3}
                  value={sceneForm.option_b_text}
                  onChange={(e) => setSceneForm((f) => ({ ...f, option_b_text: e.target.value }))}
                />
              </label>
              <div className="cms-form-actions">
                <button className="secondary" type="button" onClick={() => setEditScene(null)}>
                  取消
                </button>
                <button className="primary" type="button" disabled={busy} onClick={saveScene}>
                  保存
                </button>
              </div>
            </div>
          </div>
        </ModalOverlay>
      )}
    </div>
  );
}

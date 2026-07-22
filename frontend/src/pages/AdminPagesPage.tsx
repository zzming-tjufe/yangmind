import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import {
  getAdminPages,
  patchAdminPage,
  type AdminPage,
} from "../api/admin";
import { AdminListStatus } from "../components/AdminListStatus";
import { ModalOverlay } from "../components/ModalPortal";
import { useToast } from "../context/ToastContext";

const STATUS_LABEL: Record<string, string> = {
  published: "已发布",
  draft: "草稿",
  hidden: "隐藏",
};

export function AdminPagesPage() {
  const { toast } = useToast();
  const [pages, setPages] = useState<AdminPage[]>([]);
  const [editing, setEditing] = useState<AdminPage | null>(null);
  const [title, setTitle] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      setPages(await getAdminPages());
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

  function openEdit(p: AdminPage) {
    setEditing(p);
    setTitle(p.title);
    setSubtitle(p.subtitle);
  }

  async function saveEdit() {
    if (!editing) return;
    setBusy(true);
    try {
      await patchAdminPage(editing.id, { title, subtitle });
      setEditing(null);
      await load();
      toast("页面文案已保存");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(p: AdminPage, status: string) {
    setBusy(true);
    try {
      await patchAdminPage(p.id, { status });
      await load();
      toast(`已设为「${STATUS_LABEL[status] || status}」`);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "更新失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <section className="hero card">
        <div>
          <div className="eyebrow">PAGE CONFIG</div>
          <h2>页面管理</h2>
          <p>
            控制参与端页面的顶栏标题、副标题与发布状态。隐藏或草稿页面对普通参与者不可见。
          </p>
        </div>
      </section>

      <section className="card" style={{ marginTop: 18 }}>
        <div className="tablehead">
          <h3>参与端页面</h3>
        </div>
        <div className="manage-list">
          {loading ? (
            <AdminListStatus loading />
          ) : pages.length === 0 ? (
            <AdminListStatus empty emptyText="暂无页面配置" />
          ) : (
            pages.map((p) => (
            <div className="manage-item" key={p.id}>
              <i>{p.page_key.slice(0, 2).toUpperCase()}</i>
              <div>
                <b>
                  {p.title} <small style={{ fontWeight: 500 }}>({p.page_key})</small>
                </b>
                <small>{p.subtitle || "暂无副标题"}</small>
              </div>
              <span className={`badge ${p.status === "published" ? "" : "warn"}`}>
                {STATUS_LABEL[p.status] || p.status}
              </span>
              <div className="actions">
                <button type="button" disabled={busy} onClick={() => openEdit(p)}>
                  编辑
                </button>
                {p.status !== "published" && (
                  <button type="button" disabled={busy} onClick={() => setStatus(p, "published")}>
                    发布
                  </button>
                )}
                {p.status !== "draft" && (
                  <button type="button" disabled={busy} onClick={() => setStatus(p, "draft")}>
                    草稿
                  </button>
                )}
                {p.status !== "hidden" && (
                  <button type="button" disabled={busy} onClick={() => setStatus(p, "hidden")}>
                    隐藏
                  </button>
                )}
              </div>
            </div>
            ))
          )}
        </div>
      </section>

      {editing && (
        <ModalOverlay onClose={() => setEditing(null)}>
          <div className="profile-modal cms-modal" onClick={(e) => e.stopPropagation()}>
            <div className="profile-modal-head">
              <div className="profile-person">
                <i>▤</i>
                <div>
                  <b>编辑页面 · {editing.page_key}</b>
                  <small>修改顶栏标题与副标题</small>
                </div>
              </div>
              <button type="button" onClick={() => setEditing(null)}>
                ×
              </button>
            </div>
            <div className="cms-form">
              <label className="field">
                标题
                <input value={title} onChange={(e) => setTitle(e.target.value)} />
              </label>
              <label className="field">
                副标题
                <input value={subtitle} onChange={(e) => setSubtitle(e.target.value)} />
              </label>
              <div className="cms-form-actions">
                <button className="secondary" type="button" onClick={() => setEditing(null)}>
                  取消
                </button>
                <button className="primary" type="button" disabled={busy} onClick={saveEdit}>
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

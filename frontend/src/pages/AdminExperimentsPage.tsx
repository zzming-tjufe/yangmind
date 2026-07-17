import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import {
  getAdminExperiments,
  moveExperiment,
  patchExperiment,
  patchScene,
  type AdminExperiment,
} from "../api/admin";
import { useToast } from "../context/ToastContext";

export function AdminExperimentsPage() {
  const { toast } = useToast();
  const [items, setItems] = useState<AdminExperiment[]>([]);
  const [busy, setBusy] = useState(false);

  async function load() {
    setItems(await getAdminExperiments());
  }

  useEffect(() => {
    load().catch((e) => toast(e instanceof ApiError ? e.message : "加载失败"));
  }, [toast]);

  async function run(fn: () => Promise<unknown>, okMsg: string) {
    setBusy(true);
    try {
      await fn();
      await load();
      toast(okMsg);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <section className="hero card">
        <div>
          <div className="eyebrow">EXPERIMENT OPERATIONS</div>
          <h2>管理博弈实验</h2>
          <p>调整开放状态、轮次，以及各场景是否启用。关闭实验后参与者将无法开新局。</p>
        </div>
      </section>

      <section className="card" style={{ marginTop: 18 }}>
        <div className="tablehead">
          <h3>实验列表</h3>
          <span style={{ fontSize: 12, color: "#999" }}>使用箭头调整顺序</span>
        </div>
        <div className="manage-list">
          {items.map((exp, i) => (
            <div key={exp.id} className="manage-block">
              <div className="manage-item">
                <i>{String(i + 1).padStart(2, "0")}</i>
                <div>
                  <b>{exp.title}</b>
                  <small>
                    {exp.code} · {exp.rounds_per_scene} 轮/场景 · {exp.scenes.length} 个场景
                  </small>
                </div>
                <span className={`badge ${exp.status === "active" ? "" : "warn"}`}>
                  {exp.status === "active" ? "进行中" : exp.status === "draft" ? "草稿" : "已归档"}
                </span>
                <div className="actions">
                  <button type="button" disabled={busy} onClick={() => run(() => moveExperiment(exp.id, -1), "已上移")}>
                    ↑
                  </button>
                  <button type="button" disabled={busy} onClick={() => run(() => moveExperiment(exp.id, 1), "已下移")}>
                    ↓
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      run(
                        () =>
                          patchExperiment(exp.id, {
                            status: exp.status === "active" ? "archived" : "active",
                          }),
                        exp.status === "active" ? "已关闭实验" : "已开放实验",
                      )
                    }
                  >
                    {exp.status === "active" ? "关闭" : "开放"}
                  </button>
                </div>
              </div>
              <div className="scene-admin-list">
                {exp.scenes.map((s) => (
                  <div className="scene-admin-row" key={s.id}>
                    <span>
                      {s.no} · {s.title}
                    </span>
                    <span className={`badge ${s.enabled ? "" : "warn"}`}>
                      {s.enabled ? "启用" : "停用"}
                    </span>
                    <span className="badge">{s.required ? "必做" : "选做"}</span>
                    <button
                      className="secondary"
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        run(
                          () => patchScene(s.id, { enabled: !s.enabled }),
                          s.enabled ? "场景已停用" : "场景已启用",
                        )
                      }
                    >
                      {s.enabled ? "停用场景" : "启用场景"}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {items.length === 0 && <div className="manage-item">暂无实验</div>}
        </div>
      </section>
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import { ApiError } from "../api/client";
import { getSiteAnnouncements, type SiteAnnouncement } from "../api/admin";
import { useToast } from "../context/ToastContext";

type Filter = "all" | "notice" | "changelog";

const KIND_LABEL: Record<string, string> = {
  notice: "测试通告",
  changelog: "更新日志",
};

function formatDate(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function NoticesPage() {
  const { toast } = useToast();
  const [items, setItems] = useState<SiteAnnouncement[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getSiteAnnouncements()
      .then(setItems)
      .catch((e) => toast(e instanceof ApiError ? e.message : "加载公告失败"))
      .finally(() => setLoading(false));
  }, [toast]);

  const filtered = useMemo(() => {
    if (filter === "all") return items;
    return items.filter((x) => x.kind === filter);
  }, [items, filter]);

  return (
    <div className="page">
      <section className="hero card">
        <div>
          <div className="eyebrow">NOTICES & CHANGELOG</div>
          <h2>公告栏</h2>
          <p>查看测试相关通告与平台更新日志。置顶条目会优先显示。</p>
        </div>
      </section>

      <div className="cms-tabs">
        {(
          [
            ["all", "全部"],
            ["notice", "测试通告"],
            ["changelog", "更新日志"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={filter === id ? "active" : ""}
            onClick={() => setFilter(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {loading && <p>加载中…</p>}

      {!loading && filtered.length === 0 && (
        <section className="card notice-empty">
          <b>暂无公告</b>
          <p>有新的测试安排或版本更新时，会显示在这里。</p>
        </section>
      )}

      <div className="notice-list">
        {filtered.map((item) => (
          <article
            key={item.id}
            className={`card notice-item${item.pinned ? " is-pinned" : ""}`}
          >
            <div className="notice-meta">
              <span className={`notice-kind kind-${item.kind}`}>
                {KIND_LABEL[item.kind] || item.kind}
              </span>
              {item.pinned ? <span className="notice-pin">置顶</span> : null}
              <time>{formatDate(item.published_at)}</time>
            </div>
            <h3>{item.title}</h3>
            <div className="notice-body">{item.body || "（无正文）"}</div>
          </article>
        ))}
      </div>
    </div>
  );
}

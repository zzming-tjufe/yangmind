import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { getAccountEvents, type AccountEvent } from "../api/admin";
import { AdminListStatus } from "../components/AdminListStatus";
import { useToast } from "../context/ToastContext";

/** 总管：邀请码 / 子管等后台操作记录（与邀请码页拆开） */
export function AdminAuditPage() {
  const { toast } = useToast();
  const [events, setEvents] = useState<AccountEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const list = await getAccountEvents();
        if (!cancelled) setEvents(list);
      } catch (e) {
        if (!cancelled) {
          toast(e instanceof ApiError ? e.message : "加载失败");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [toast]);

  return (
    <div className="page">
      <div className="settings">
        <article className="setting card">
          <i>录</i>
          <h3>这是什么</h3>
          <p>创建邀请码、分配、启停等操作会记在这里，方便事后核对，不是登录记录。</p>
        </article>
      </div>

      <section className="table card" style={{ marginTop: 18 }}>
        <div className="tablehead">
          <h3>操作记录</h3>
          <span style={{ opacity: 0.65, fontSize: 13 }}>{events.length} 条</span>
        </div>
        <div className="row header event-row">
          <span>事件</span>
          <span>时间</span>
        </div>
        {loading ? (
          <AdminListStatus loading />
        ) : events.length === 0 ? (
          <AdminListStatus empty emptyText="暂无操作记录" />
        ) : (
          events.map((ev) => (
            <div className="row event-row" key={ev.id}>
              <span className="event-copy">
                <b>{ev.title || ev.event_type}</b>
                <small>{ev.detail || "无更多说明"}</small>
              </span>
              <span className="event-time">
                {ev.created_at
                  ? new Date(ev.created_at).toLocaleString("zh-CN", {
                      year: "numeric",
                      month: "2-digit",
                      day: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "—"}
              </span>
            </div>
          ))
        )}
      </section>
    </div>
  );
}

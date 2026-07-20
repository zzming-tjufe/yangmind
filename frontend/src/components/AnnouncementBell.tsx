import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError } from "../api/client";
import { getSiteAnnouncements, type SiteAnnouncement } from "../api/admin";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

const KIND_LABEL: Record<string, string> = {
  notice: "测试通告",
  changelog: "更新日志",
};

function storageKey(userId: number) {
  return `ym_ann_seen_v1_${userId}`;
}

function readSeen(userId: number): number[] {
  try {
    const raw = localStorage.getItem(storageKey(userId));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x): x is number => typeof x === "number");
  } catch {
    return [];
  }
}

function writeSeen(userId: number, ids: number[]) {
  localStorage.setItem(storageKey(userId), JSON.stringify([...new Set(ids)]));
}

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

type Props = {
  /** 顶栏右侧插槽以外也可单独使用 */
  className?: string;
};

/**
 * 右上角公告入口：
 * - 新发布的公告自动弹窗一次，关闭后记入本机已读，不再自动弹出
 * - 随时可点按钮再次查看全部公告
 */
export function AnnouncementBell({ className }: Props) {
  const { user } = useAuth();
  const { toast } = useToast();
  const [items, setItems] = useState<SiteAnnouncement[]>([]);
  const [seen, setSeen] = useState<number[]>([]);
  const [open, setOpen] = useState(false);
  const [autoMode, setAutoMode] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const userId = user?.id;

  const reload = useCallback(async () => {
    if (userId == null) return;
    const list = await getSiteAnnouncements();
    setItems(list);
    setSeen(readSeen(userId));
    setLoaded(true);
  }, [userId]);

  useEffect(() => {
    reload().catch((e) => {
      if (e instanceof ApiError) toast(e.message);
    });
  }, [reload, toast]);

  const unread = useMemo(
    () => items.filter((x) => !seen.includes(x.id)),
    [items, seen],
  );

  // 有未读时自动弹出一次
  useEffect(() => {
    if (!loaded || userId == null) return;
    if (unread.length === 0) return;
    setAutoMode(true);
    setOpen(true);
  }, [loaded, unread.length, userId]);

  function markCurrentUnreadSeen() {
    if (userId == null || unread.length === 0) return;
    const next = [...seen, ...unread.map((x) => x.id)];
    writeSeen(userId, next);
    setSeen(readSeen(userId));
  }

  function closePanel() {
    markCurrentUnreadSeen();
    setAutoMode(false);
    setOpen(false);
  }

  function openManual() {
    setAutoMode(false);
    setOpen(true);
  }

  const displayItems = autoMode && unread.length > 0 ? unread : items;

  return (
    <>
      <button
        type="button"
        className={`ann-bell${className ? ` ${className}` : ""}${unread.length ? " has-unread" : ""}`}
        onClick={openManual}
        aria-label={unread.length ? `公告，${unread.length} 条未读` : "查看公告"}
        title="公告"
      >
        <span className="ann-bell-label">公告</span>
        {unread.length > 0 ? <em className="ann-bell-dot">{unread.length}</em> : null}
      </button>

      {open && (
        <div className="profile-overlay ann-overlay" onClick={closePanel}>
          <div
            className="profile-modal cms-modal ann-panel"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal
            aria-labelledby="ann-panel-title"
          >
            <div className="profile-modal-head">
              <div className="profile-person">
                <i>!</i>
                <div>
                  <b id="ann-panel-title">{autoMode ? "新公告" : "公告栏"}</b>
                  <small>
                    {autoMode
                      ? "本次更新内容，关闭后不再自动弹出"
                      : "可随时从右上角再次打开"}
                  </small>
                </div>
              </div>
              <button type="button" onClick={closePanel} aria-label="关闭">
                ×
              </button>
            </div>
            <div className="ann-panel-body">
              {displayItems.length === 0 && (
                <div className="notice-empty" style={{ border: 0, boxShadow: "none" }}>
                  <b>暂无公告</b>
                  <p>有新的测试安排或版本更新时会显示在这里。</p>
                </div>
              )}
              {displayItems.map((item) => (
                <article key={item.id} className={`ann-panel-item${item.pinned ? " is-pinned" : ""}`}>
                  <div className="notice-meta">
                    <span className={`notice-kind kind-${item.kind}`}>
                      {KIND_LABEL[item.kind] || item.kind}
                    </span>
                    {item.pinned ? <span className="notice-pin">置顶</span> : null}
                    {!seen.includes(item.id) ? <span className="notice-pin">新</span> : null}
                    <time>{formatDate(item.published_at)}</time>
                  </div>
                  <h3>{item.title}</h3>
                  <div className="notice-body">{item.body || "（无正文）"}</div>
                </article>
              ))}
            </div>
            <div className="ann-panel-foot">
              <button className="primary" type="button" onClick={closePanel}>
                {autoMode ? "我知道了" : "关闭"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

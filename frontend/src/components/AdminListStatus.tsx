/** 管理端列表加载中 / 空态（全宽，避免挤在 manage-item 左侧） */
export function AdminListStatus({
  loading,
  empty,
  emptyText,
  message,
  page,
}: {
  loading?: boolean;
  empty?: boolean;
  emptyText?: string;
  message?: string;
  /** 首屏级占位，更高更醒目 */
  page?: boolean;
}) {
  if (loading) {
    return (
      <div
        className={`admin-list-status${page ? " is-page" : ""}`}
        role="status"
        aria-live="polite"
      >
        <span className="admin-spinner" aria-hidden />
        <span>{message || "加载中…"}</span>
      </div>
    );
  }
  if (empty) {
    return (
      <div className={`admin-list-status is-empty${page ? " is-page" : ""}`}>
        <span>{emptyText || "暂无数据"}</span>
      </div>
    );
  }
  return null;
}

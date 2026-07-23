import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { getLeaderboard, type LeaderboardEntry } from "../api/admin";
import { useToast } from "../context/ToastContext";
import { useSiteContent } from "../hooks/useSite";

type Period = "weekly" | "all";

export function RankPage() {
  const { toast } = useToast();
  const { byKey: content } = useSiteContent();
  const [period, setPeriod] = useState<Period>("weekly");
  const [items, setItems] = useState<LeaderboardEntry[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getLeaderboard(period)
      .then((res) => setItems(res.items))
      .catch((e) => toast(e instanceof ApiError ? e.message : "加载排行榜失败"))
      .finally(() => setLoading(false));
  }, [period, toast]);

  const filtered = items.filter(
    (x) => !q || x.nickname.includes(q) || x.public_id.includes(q),
  );
  const hero = content["rank.hero"];

  return (
    <div className="page">
      <section className="hero card page-soft-in">
        <div>
          <div className="eyebrow">
            {period === "weekly" ? "本周排行" : "总排行"}
          </div>
          <h2>{hero?.title || "合作不只是策略，也是成绩"}</h2>
          <p>
            {period === "weekly"
              ? "本周榜统计本周一以来已完成对局的累计得分（按场次与得分排序）。"
              : hero?.body ||
                "总榜统计历史全部已完成对局的累计得分、场次与人格摘要。"}
          </p>
        </div>
        <div className="ring" style={{ ["--p" as string]: "278deg" }}>
          <b>#{filtered[0]?.rank ?? "-"}</b>
        </div>
      </section>

      <div className="cms-tabs">
        <button
          type="button"
          className={period === "weekly" ? "active" : ""}
          onClick={() => setPeriod("weekly")}
        >
          本周榜
        </button>
        <button
          type="button"
          className={period === "all" ? "active" : ""}
          onClick={() => setPeriod("all")}
        >
          总榜
        </button>
      </div>

      <section className="card">
        <div className="tablehead">
          <h3>{period === "weekly" ? "本周排行" : "总排行榜"}</h3>
          <input
            className="search"
            placeholder="搜索参与者"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <div className="row header rank-row">
          <span>参与者</span>
          <span>排名</span>
          <span>场次</span>
          <span>人格摘要</span>
          <span>{period === "weekly" ? "本周得分" : "总得分"}</span>
        </div>
        {loading && (
          <div className="row" style={{ gridTemplateColumns: "1fr" }}>
            <span>加载中…</span>
          </div>
        )}
        {!loading &&
          filtered.map((u, i) => (
            <div
              className="row rank-row rank-row-in"
              key={`${period}-${u.public_id}`}
              style={{ animationDelay: `${Math.min(i, 12) * 0.04}s` }}
            >
              <span className="user">
                <i>{u.nickname.slice(0, 1)}</i>
                <b>{u.nickname}</b>
              </span>
              <b>#{u.rank}</b>
              <span>{u.sessions_count}</span>
              <span>{u.personality_summary}</span>
              <b>{u.total_score}</b>
            </div>
          ))}
        {!loading && filtered.length === 0 && (
          <div className="row" style={{ gridTemplateColumns: "1fr" }}>
            <span>{period === "weekly" ? "本周暂无已完成对局" : "暂无数据"}</span>
          </div>
        )}
      </section>
    </div>
  );
}

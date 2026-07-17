import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { getLeaderboard, type LeaderboardEntry } from "../api/admin";
import { useToast } from "../context/ToastContext";
import { useSiteContent } from "../hooks/useSite";

export function RankPage() {
  const { toast } = useToast();
  const { byKey: content } = useSiteContent();
  const [items, setItems] = useState<LeaderboardEntry[]>([]);
  const [q, setQ] = useState("");

  useEffect(() => {
    getLeaderboard()
      .then((res) => setItems(res.items))
      .catch((e) => toast(e instanceof ApiError ? e.message : "加载排行榜失败"));
  }, [toast]);

  const filtered = items.filter(
    (x) => !q || x.nickname.includes(q) || x.public_id.includes(q),
  );
  const hero = content["rank.hero"];

  return (
    <div className="page">
      <section className="hero card">
        <div>
          <div className="eyebrow">WEEKLY LEADERBOARD</div>
          <h2>{hero?.title || "合作不只是策略，也是成绩"}</h2>
          <p>
            {hero?.body ||
              "排行榜综合累计得分、有效场次与人格摘要（来自真实后端数据）。"}
          </p>
        </div>
        <div className="ring" style={{ ["--p" as string]: "278deg" }}>
          <b>#{filtered[0]?.rank ?? "-"}</b>
        </div>
      </section>
      <section className="table card" style={{ marginTop: 18 }}>
        <div className="tablehead">
          <h3>总排行榜</h3>
          <input
            className="search"
            placeholder="搜索参与者"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <div className="row header">
          <span>参与者</span>
          <span>排名</span>
          <span>场次</span>
          <span>人格摘要</span>
          <span>总得分</span>
          <span>趋势</span>
        </div>
        {filtered.map((u) => (
          <div className="row" key={u.public_id}>
            <span className="user">
              <i>{u.nickname.slice(0, 1)}</i>
              <b>{u.nickname}</b>
            </span>
            <b>#{u.rank}</b>
            <span>{u.sessions_count}</span>
            <span>{u.personality_summary}</span>
            <b>{u.total_score}</b>
            <span style={{ color: "#269c7d" }}>↑</span>
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="row" style={{ gridTemplateColumns: "1fr" }}>
            <span>暂无数据</span>
          </div>
        )}
      </section>
    </div>
  );
}

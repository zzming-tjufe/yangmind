import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";
import * as gamesApi from "../api/games";
import type { Scene, Session, StagProgress } from "../api/games";
import { useToast } from "../context/ToastContext";
import { useSiteContent } from "../hooks/useSite";

type Stage = "lobby" | "scenes" | "intro" | "play";

export function GamesPage() {
  const { toast } = useToast();
  const { byKey: content } = useSiteContent();
  const [progress, setProgress] = useState<StagProgress | null>(null);
  const [stage, setStage] = useState<Stage>("lobby");
  const [scene, setScene] = useState<Scene | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    const data = await gamesApi.getScenes();
    setProgress(data);
    return data;
  }, []);

  useEffect(() => {
    reload()
      .catch((e) => toast(e instanceof ApiError ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [reload, toast]);

  async function enterStag() {
    if (!progress?.unlock_games) {
      toast("请先完成 BFI-44 问卷");
      return;
    }
    setStage("scenes");
  }

  async function openScene(s: Scene) {
    if (s.completed && progress && !progress.all_done) {
      toast("该场景已完成，请先完成另一个必做场景");
      return;
    }
    setBusy(true);
    try {
      const sess = await gamesApi.startSession(s.scene_key);
      setScene(s);
      setSession(sess);
      setStage(sess.history.length > 0 ? "play" : "intro");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "开局失败");
    } finally {
      setBusy(false);
    }
  }

  async function play(choice: "A" | "B") {
    if (!session) return;
    setBusy(true);
    try {
      const next = await gamesApi.playRound(session.id, choice);
      setSession(next);
      if (next.status === "finished") {
        await reload();
        toast(next.experiment_all_done ? "两个场景均已完成" : "本场景完成");
      }
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "提交失败");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <div className="page"><p>加载中…</p></div>;

  if (stage === "lobby") {
    const lobby = content["games.lobby"];
    return (
      <div className="page">
        {!progress?.unlock_games && (
          <div className="alert">
            <i>!</i>
            <div>
              <b>博弈入口暂未解锁</b>
              <small>完成 BFI-44 问卷后即可进入全部实验。</small>
            </div>
          </div>
        )}
        <div className="section-head">
          <div>
            <div className="eyebrow">EXPERIMENT LOBBY</div>
            <h2>{lobby?.title || "选择一种博弈"}</h2>
            <p>{lobby?.body || "观察在不同收益结构下，你如何建立信任、权衡风险。"}</p>
          </div>
        </div>
        <div className="games">
          <article className={`game card ${progress?.unlock_games ? "" : "locked"}`}>
            <div className="art prison">
              <span>01 · PRISONER</span>
              <div className="bars">
                {Array.from({ length: 5 }, (_, i) => (
                  <i key={i} />
                ))}
              </div>
            </div>
            <div className="gamebody">
              <span>非零和 · 同时行动</span>
              <h3>囚徒困境</h3>
              <p>合作带来稳定收益，单方面背叛可能获得更高回报。</p>
              <button
                className="primary"
                type="button"
                onClick={() => toast("囚徒困境将在后续版本补充完整对局")}
              >
                后续开放 →
              </button>
            </div>
          </article>
          <article className={`game card ${progress?.unlock_games ? "" : "locked"}`}>
            <div className="art stag">
              <span>02 · STAG HUNT</span>
              <div className="forest" />
            </div>
            <div className="gamebody">
              <span>协调博弈 · 收益依赖</span>
              <h3>猎鹿博弈</h3>
              <p>包含「双人小组任务」和「出行安排」两个完整场景。</p>
              <div className="stats">
                <span>
                  <b>{progress?.done_count ?? 0}/{progress?.required_count ?? 2}</b>
                  进度
                </span>
                <span>
                  <b>2</b>个场景
                </span>
                <span>
                  <b>10/6/0</b>计分
                </span>
              </div>
              <button className="primary" type="button" onClick={enterStag}>
                {progress?.unlock_games ? "选择场景 →" : "完成问卷后解锁 →"}
              </button>
            </div>
          </article>
        </div>
      </div>
    );
  }

  if (stage === "scenes" && progress) {
    return (
      <div className="page">
        <button className="backbtn" type="button" onClick={() => setStage("lobby")}>
          ← 返回博弈大厅
        </button>
        <div className="section-head">
          <div>
            <div className="eyebrow">STAG HUNT · TWO REQUIRED SCENARIOS</div>
            <h2>完成两个猎鹿博弈场景</h2>
            <p>两个场景均为必做项目，每个场景需要完整进行 10 轮。</p>
          </div>
        </div>
        <div className={`completion-banner card ${progress.all_done ? "complete" : ""}`}>
          <div>
            <span>{progress.all_done ? "EXPERIMENT COMPLETE" : "REQUIRED PROGRESS"}</span>
            <b>
              {progress.all_done
                ? "两个场景均已完成"
                : `必做进度：${progress.done_count} / ${progress.required_count}`}
            </b>
            <small>
              {progress.all_done
                ? "猎鹿博弈实验已计为完整完成。"
                : "只有两个场景分别完成后才计为实验完成。"}
            </small>
          </div>
          <strong>
            {progress.done_count}/{progress.required_count}
          </strong>
        </div>
        <div className="scene-grid">
          {progress.scenes.map((s) => {
            const blocked = s.completed && !progress.all_done;
            return (
              <article
                key={s.scene_key}
                className={`scenario-card card ${s.completed ? "completed" : ""}`}
                data-no={s.no}
              >
                <span className="scenario-status">{s.completed ? "✓ 已完成" : "○ 必做场景"}</span>
                <h3>{s.title}</h3>
                <p>{s.short_desc}</p>
                <div className="scenario-meta">
                  <i>10 轮</i>
                  <i>同时选择</i>
                  <i>{s.completed ? `得分 ${s.best_score}` : "A / B"}</i>
                </div>
                <button
                  className="primary"
                  type="button"
                  disabled={blocked || busy}
                  onClick={() => openScene(s)}
                >
                  {blocked
                    ? "已完成，请继续另一场景"
                    : s.completed
                      ? "重新体验该场景 →"
                      : "查看场景规则 →"}
                </button>
              </article>
            );
          })}
        </div>
      </div>
    );
  }

  if (stage === "intro" && scene && session) {
    return (
      <div className="page">
        <button className="backbtn" type="button" onClick={() => setStage("scenes")}>
          ← 返回场景选择
        </button>
        <section className="hero card">
          <div>
            <div className="eyebrow">猎鹿博弈 · 场景 {scene.no}</div>
            <h2>{scene.title}</h2>
            <p>{scene.short_desc}每轮你不能提前知道对方的选择。</p>
          </div>
          <div className="ring" style={{ ["--p" as string]: "0deg" }}>
            <b>0/10</b>
          </div>
        </section>
        <div className="rule-layout" style={{ marginTop: 18 }}>
          <section className="rule-copy card">
            <h3>你的两个选择</h3>
            <div className="options">
              <div className="option">
                <b>A：{scene.option_a}</b>
                <span>{scene.option_a_text}</span>
              </div>
              <div className="option">
                <b>B：{scene.option_b}</b>
                <span>{scene.option_b_text}</span>
              </div>
            </div>
          </section>
          <section className="matrix-card card">
            <h3>每轮得分规则</h3>
            <div className="matrix">
              <div className="matrix-row head">
                <span>你 / 对方</span>
                <span>A</span>
                <span>B</span>
              </div>
              <div className="matrix-row">
                <span>A</span>
                <span>10 / 10</span>
                <span>0 / 6</span>
              </div>
              <div className="matrix-row">
                <span>B</span>
                <span>6 / 0</span>
                <span>6 / 6</span>
              </div>
            </div>
          </section>
        </div>
        <div className="rule-actions">
          <small>请确认你已了解场景和计分规则。</small>
          <button className="primary" type="button" onClick={() => setStage("play")}>
            我已了解，开始第 1 轮 →
          </button>
        </div>
      </div>
    );
  }

  if (stage === "play" && scene && session) {
    if (session.status === "finished") {
      return (
        <div className="page">
          <section className="finish card">
            <div className="trophy">{session.experiment_all_done ? "✓" : "✦"}</div>
            <div className="eyebrow" style={{ justifyContent: "center", marginTop: 20 }}>
              {session.experiment_all_done
                ? "猎鹿博弈已全部完成"
                : `场景已完成 · 总进度 ${(progress?.done_count ?? 0)}/${progress?.required_count ?? 2}`}
            </div>
            <h2>{scene.title} · 10 轮结束</h2>
            <div className="finish-score">{session.my_score} 分</div>
            <p>
              本场对方得分：{session.opponent_score} · 你选择 A：
              {session.history.filter((h) => h.my_choice === "A").length} 次
            </p>
            <div className="finish-actions">
              <button className="secondary" type="button" onClick={() => setStage("scenes")}>
                查看场景进度
              </button>
              <button
                className="primary"
                type="button"
                onClick={() => {
                  const next = progress?.scenes.find((s) => !s.completed);
                  if (next) openScene(next);
                  else setStage("scenes");
                }}
              >
                {session.experiment_all_done ? "返回场景列表" : "继续下一个必做场景 →"}
              </button>
            </div>
          </section>
        </div>
      );
    }

    const history = [...session.history].reverse();
    return (
      <div className="page">
        <button
          className="backbtn"
          type="button"
          onClick={async () => {
            if (session) await gamesApi.abandonSession(session.id).catch(() => undefined);
            setStage("scenes");
          }}
        >
          ← 退出当前对局
        </button>
        <section className="round-card card">
          <div className="roundtop">
            <div>
              <div className="eyebrow">{scene.title}</div>
              <h2>现在是第 {session.current_round} 轮</h2>
              <p>请同时做出决策：你选择 A 还是 B？</p>
            </div>
            <div className="roundbadge">
              第 <b>{session.current_round}</b> / {session.rounds_total} 轮
            </div>
          </div>
          <div className="scoreboard">
            <div className="scorebox">
              <span>你的累计得分</span>
              <b>{session.my_score}</b>
            </div>
            <div className="versus">VS</div>
            <div className="scorebox">
              <span>对方累计得分</span>
              <b>{session.opponent_score}</b>
            </div>
          </div>
          {session.last_round && (
            <div className="last-result">
              上一轮：你选择 <b>{session.last_round.my_choice}</b>，对方选择{" "}
              <b>{session.last_round.opponent_choice}</b>。你得{" "}
              <b>{session.last_round.my_points}</b> 分，对方得{" "}
              <b>{session.last_round.opponent_points}</b> 分。
            </div>
          )}
          <div className="choice-title">请选择本轮行动</div>
          <div className="choice-buttons">
            <button className="choice-btn" type="button" disabled={busy} onClick={() => play("A")}>
              <b>A · {scene.option_a}</b>
              <span>{scene.option_a_text}</span>
              <em>双方选 A：10 分</em>
            </button>
            <button className="choice-btn" type="button" disabled={busy} onClick={() => play("B")}>
              <b>B · {scene.option_b}</b>
              <span>{scene.option_b_text}</span>
              <em>稳定收益：6 分</em>
            </button>
          </div>
        </section>
        {history.length > 0 && (
          <section className="history-card card">
            <div className="history-title">之前轮次的记录</div>
            <div className="history-row head">
              <span>轮次</span>
              <span>你的选择</span>
              <span>对方选择</span>
              <span>你的得分</span>
              <span>对方得分</span>
            </div>
            {history.map((h) => (
              <div className="history-row" key={h.round_no}>
                <span>{h.round_no}</span>
                <span>
                  <i className={`choice-tag ${h.my_choice === "B" ? "b" : ""}`}>{h.my_choice}</i>
                </span>
                <span>
                  <i className={`choice-tag ${h.opponent_choice === "B" ? "b" : ""}`}>
                    {h.opponent_choice}
                  </i>
                </span>
                <b>+{h.my_points}</b>
                <b>+{h.opponent_points}</b>
              </div>
            ))}
          </section>
        )}
      </div>
    );
  }

  return null;
}

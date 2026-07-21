import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";
import * as gamesApi from "../api/games";
import type { Comprehension, PvpMatch, Scene, StagProgress } from "../api/games";
import { useToast } from "../context/ToastContext";
import { useSiteContent } from "../hooks/useSite";

type Stage = "lobby" | "comprehension" | "scenes" | "matching" | "matched" | "pvp";

/** 用服务端 seconds_left 校准，本地平滑跳动，避免每秒整跳。 */
function useLocalSeconds(secondsLeft: number | null | undefined, syncKey: string) {
  const [left, setLeft] = useState(secondsLeft ?? 0);
  const endsAt = useRef<number | null>(null);

  useEffect(() => {
    if (secondsLeft == null) {
      endsAt.current = null;
      setLeft(0);
      return;
    }
    endsAt.current = Date.now() + secondsLeft * 1000;
    setLeft(secondsLeft);
  }, [secondsLeft, syncKey]);

  useEffect(() => {
    if (endsAt.current == null) return;
    const tick = () => {
      if (endsAt.current == null) return;
      setLeft(Math.max(0, Math.ceil((endsAt.current - Date.now()) / 1000)));
    };
    tick();
    const id = window.setInterval(tick, 200);
    return () => window.clearInterval(id);
  }, [syncKey, secondsLeft]);

  return left;
}

function useElapsedSeconds(active: boolean) {
  const [sec, setSec] = useState(0);
  useEffect(() => {
    if (!active) {
      setSec(0);
      return;
    }
    setSec(0);
    const started = Date.now();
    const id = window.setInterval(() => setSec(Math.floor((Date.now() - started) / 1000)), 500);
    return () => window.clearInterval(id);
  }, [active]);
  return sec;
}

export function GamesPage() {
  const { toast } = useToast();
  const { byKey: content } = useSiteContent();
  const [progress, setProgress] = useState<StagProgress | null>(null);
  const [stage, setStage] = useState<Stage>("lobby");
  const [scene, setScene] = useState<Scene | null>(null);
  const [pvp, setPvp] = useState<PvpMatch | null>(null);
  const [comprehension, setComprehension] = useState<Comprehension | null>(null);
  const [comprehensionAnswers, setComprehensionAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const lastHistLen = useRef(0);
  const matchFlashTimer = useRef<number | null>(null);
  const zeroPollKey = useRef("");
  const matchNotifiedId = useRef<number | null>(null);

  const waitSec = useElapsedSeconds(stage === "matching");
  const syncKey = pvp ? `${pvp.id}-${pvp.current_round}-${pvp.round_deadline ?? ""}` : "";
  const secondsLeft = useLocalSeconds(
    stage === "pvp" && pvp?.status === "playing" ? pvp.seconds_left : null,
    syncKey,
  );

  const bindScene = useCallback(
    (m: PvpMatch, fallback?: Scene | null) => {
      const fromProgress = progress?.scenes.find((s) => s.scene_key === m.scene_key);
      if (fromProgress) {
        setScene(fromProgress);
        return fromProgress;
      }
      if (fallback && fallback.scene_key === m.scene_key) {
        setScene(fallback);
        return fallback;
      }
      return null;
    },
    [progress],
  );

  const enterMatchedFlash = useCallback(
    (m: PvpMatch) => {
      if (matchNotifiedId.current === m.id) {
        setStage("pvp");
        return;
      }
      matchNotifiedId.current = m.id;
      setStage("matched");
      toast(`已匹配到 ${m.opponent_nickname || "对手"}`);
      if (matchFlashTimer.current) window.clearTimeout(matchFlashTimer.current);
      matchFlashTimer.current = window.setTimeout(() => setStage("pvp"), 1100);
    },
    [toast],
  );

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

  useEffect(() => {
    return () => {
      if (matchFlashTimer.current) window.clearTimeout(matchFlashTimer.current);
    };
  }, []);

  useEffect(() => {
    if ((stage !== "matching" && stage !== "matched" && stage !== "pvp") || !pvp) return;
    if (pvp.status === "finished" || pvp.status === "cancelled") return;

    const matchId = pvp.id;
    const timer = window.setInterval(() => {
      gamesApi
        .getPvpMatch(matchId)
        .then((m) => {
          if (m.id !== matchId) {
            lastHistLen.current = 0;
            toast(`第一场景已完成，继续与同一对手进入「${m.scene_title}」`);
          }
          setPvp(m);
          bindScene(m);
          if (m.status === "playing" && (stage === "matching" || stage === "matched")) {
            if (stage === "matching") enterMatchedFlash(m);
          }
          if (m.status === "finished") {
            reload().catch(() => undefined);
          }
        })
        .catch(() => undefined);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [stage, pvp?.id, pvp?.status, reload, bindScene, enterMatchedFlash, toast]);

  // 轮次结算 / 超时提示
  useEffect(() => {
    if (!pvp || stage !== "pvp") {
      lastHistLen.current = pvp?.history.length ?? 0;
      return;
    }
    const len = pvp.history.length;
    if (len > lastHistLen.current) {
      const latest = pvp.history[len - 1];
      if (latest?.my_timed_out) toast("本轮超时未选，得 0 分");
      else if (latest?.opponent_timed_out) toast("对方超时，本轮已按规则结算");
    }
    lastHistLen.current = len;
  }, [pvp, stage, toast]);

  // 倒计时归零时立刻拉一次，尽快触发超时结算
  useEffect(() => {
    if (stage !== "pvp" || !pvp || pvp.status !== "playing") return;
    if (secondsLeft > 0) return;
    const key = `${pvp.id}-${pvp.current_round}`;
    if (zeroPollKey.current === key) return;
    zeroPollKey.current = key;
    gamesApi
      .getPvpMatch(pvp.id)
      .then((m) => {
        setPvp(m);
        bindScene(m);
      })
      .catch(() => undefined);
  }, [secondsLeft, stage, pvp, bindScene]);

  async function enterStag() {
    if (!progress?.unlock_games) {
      toast(
        progress?.survey_quality_failed
          ? "本次问卷未达到真人博弈的数据质量要求"
          : !progress?.survey_done
            ? "请先完成 BFI-44 问卷"
            : progress?.experiment_status !== "active"
              ? "实验暂未开放"
              : "当前无法开始",
      );
      return;
    }
    if (!progress.comprehension_passed) {
      setBusy(true);
      try {
        const check = await gamesApi.getComprehension();
        setComprehension(check);
        if (check.passed) {
          await reload();
          setStage("scenes");
        } else {
          setStage("comprehension");
        }
      } catch (e) {
        toast(e instanceof ApiError ? e.message : "加载理解检查失败");
      } finally {
        setBusy(false);
      }
      return;
    }
    setStage("scenes");
  }

  async function checkComprehension() {
    if (!comprehension) return;
    const missing = comprehension.questions.find(
      (question) => !comprehensionAnswers[question.question_id],
    );
    if (missing) {
      toast("请完成全部理解检查题");
      return;
    }
    setBusy(true);
    try {
      const result = await gamesApi.submitComprehension(comprehensionAnswers);
      setComprehension(result);
      if (result.passed) {
        await reload();
        toast("理解检查已通过，可以进入真人匹配");
        setStage("scenes");
      } else {
        toast(`还有 ${result.incorrect_ids.length} 题不正确，请根据规则重新检查`);
      }
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "提交理解检查失败");
    } finally {
      setBusy(false);
    }
  }

  async function startPvp(s: Scene) {
    setBusy(true);
    setScene(s);
    lastHistLen.current = 0;
    zeroPollKey.current = "";
    matchNotifiedId.current = null;
    try {
      const m = await gamesApi.joinPvpQueue(s.scene_key);
      setPvp(m);
      bindScene(m, s);
      if (m.resumed && m.status === "playing") {
        toast("继续未完成的对局");
        setStage("pvp");
        return;
      }
      if (m.resumed && m.status === "waiting") {
        toast("你仍在匹配队列中");
        setStage("matching");
        return;
      }
      if (m.status === "playing") {
        enterMatchedFlash(m);
      } else {
        setStage("matching");
      }
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "匹配失败");
      setStage("scenes");
    } finally {
      setBusy(false);
    }
  }

  async function playPvp(choice: "A" | "B") {
    if (!pvp) return;
    if (secondsLeft <= 0) {
      toast("本轮已超时");
      return;
    }
    setBusy(true);
    try {
      const next = await gamesApi.submitPvpChoice(pvp.id, choice, pvp.current_round);
      if (next.id !== pvp.id) {
        lastHistLen.current = 0;
        toast(`第一场景已完成，继续与同一对手进入「${next.scene_title}」`);
      }
      setPvp(next);
      bindScene(next);
      if (next.status === "finished") {
        await reload();
        toast("真人对局已结束");
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        toast(e.message);
        const fresh = await gamesApi.getPvpMatch(pvp.id).catch(() => null);
        if (fresh) {
          setPvp(fresh);
          bindScene(fresh);
        }
      } else {
        toast(e instanceof ApiError ? e.message : "提交失败");
      }
    } finally {
      setBusy(false);
    }
  }

  async function cancelMatching() {
    try {
      const res = await gamesApi.cancelPvpQueue();
      if (res.cancelled) {
        setPvp(null);
        setStage("scenes");
        return;
      }
      if (res.status === "playing" && res.match_id) {
        toast(res.detail || "已匹配成功，无法取消");
        const m = await gamesApi.getPvpMatch(res.match_id);
        setPvp(m);
        bindScene(m);
        enterMatchedFlash(m);
        return;
      }
      setPvp(null);
      setStage("scenes");
    } catch {
      toast("取消失败");
    }
  }

  if (loading) return <div className="page"><p>加载中…</p></div>;

  if (stage === "lobby") {
    const lobby = content["games.lobby"];
    return (
      <div className="page page-soft-in">
        {!progress?.unlock_games && (
          <div className="alert">
            <i>!</i>
            <div>
              <b>
                {progress?.survey_quality_failed
                  ? "本次实验资格审核未通过"
                  : !progress?.survey_done
                    ? "博弈入口暂未解锁"
                    : progress?.experiment_status !== "active"
                      ? "实验暂未开放"
                      : "博弈入口暂未解锁"}
              </b>
              <small>
                {progress?.survey_quality_failed
                  ? "该答卷不会进入人格对决样本，也无法进入真人匹配；如遇技术故障请联系实验管理员。"
                  : !progress?.survey_done
                    ? "完成 BFI-44 问卷后即可进入全部实验。"
                    : progress?.experiment_status !== "active"
                      ? "管理员已关闭本实验，请稍后再试或联系实验组织者。"
                      : "当前无法开始新对局。"}
              </small>
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
              <span>协调博弈 · 真人匹配</span>
              <h3>猎鹿博弈</h3>
              <p>匹配在线参与者同步对局；每轮 15 秒，超时未选本轮得 0 分。</p>
              <div className="stats">
                <span>
                  <b>{progress?.rounds_per_scene ?? 10}</b>轮/场
                </span>
                <span>
                  <b>真人</b>匹配
                </span>
                <span>
                  <b>15</b>秒/轮
                </span>
              </div>
              <button className="primary" type="button" onClick={enterStag}>
                {progress?.unlock_games
                  ? progress.active_match_id
                    ? "继续正式实验 →"
                    : progress.all_done || progress.participation_locked
                      ? "查看实验状态 →"
                      : "进入唯一一次正式实验 →"
                  : progress?.survey_quality_failed
                    ? "无法进入真人匹配"
                    : "完成问卷后解锁 →"}
              </button>
            </div>
          </article>
        </div>
      </div>
    );
  }

  if (stage === "comprehension" && comprehension) {
    const incorrect = new Set(comprehension.incorrect_ids);
    return (
      <div className="page page-soft-in">
        <button className="backbtn" type="button" onClick={() => setStage("lobby")}>
          ← 返回博弈大厅
        </button>
        <section className="hero card">
          <div>
            <div className="eyebrow">COMPREHENSION CHECK</div>
            <h2>猎鹿博弈规则理解检查</h2>
            <p>全部答对后才能进入真人匹配。答错可以复习规则后再次检查，不影响人格问卷。</p>
          </div>
        </section>

        <div className="card" style={{ marginTop: 18, padding: 20 }}>
          <h3 style={{ marginTop: 0 }}>得分规则</h3>
          <p>A/A：双方各 10 分；A/B：A 方 0 分、B 方 6 分；B/B：双方各 6 分。</p>
          <p style={{ marginBottom: 0 }}>每轮双方同时独立选择，不能提前看到对方本轮选择。</p>
        </div>

        <div style={{ display: "grid", gap: 14, marginTop: 18 }}>
          {comprehension.questions.map((question, index) => (
            <section
              className="card"
              key={question.question_id}
              style={{
                padding: 20,
                borderColor: incorrect.has(question.question_id) ? "#d95c5c" : undefined,
              }}
            >
              <h3 style={{ marginTop: 0 }}>
                {index + 1}. {question.prompt}
              </h3>
              <div style={{ display: "grid", gap: 8 }}>
                {question.options.map((option) => (
                  <label key={option.value} style={{ display: "flex", gap: 9, alignItems: "center" }}>
                    <input
                      type="radio"
                      name={`comprehension-${question.question_id}`}
                      value={option.value}
                      checked={comprehensionAnswers[question.question_id] === option.value}
                      onChange={() =>
                        setComprehensionAnswers((previous) => ({
                          ...previous,
                          [question.question_id]: option.value,
                        }))
                      }
                    />
                    <span>{option.label}</span>
                  </label>
                ))}
              </div>
              {incorrect.has(question.question_id) && (
                <small style={{ color: "#c94848" }}>本题不正确，请对照上方规则重新选择。</small>
              )}
            </section>
          ))}
        </div>
        <button
          className="primary"
          type="button"
          disabled={busy}
          onClick={checkComprehension}
          style={{ marginTop: 18 }}
        >
          {busy ? "检查中…" : "提交理解检查"}
        </button>
      </div>
    );
  }

  if (stage === "scenes" && progress) {
    const firstRequiredScene = progress.scenes.find((item) => item.required);
    const cannotResume =
      progress.participation_locked && !progress.active_match_id && !progress.all_done;
    return (
      <div className="page page-soft-in">
        <button className="backbtn" type="button" onClick={() => setStage("lobby")}>
          ← 返回博弈大厅
        </button>
        <div className="section-head">
          <div>
            <div className="eyebrow">STAG HUNT · PVP</div>
            <h2>猎鹿博弈 · 真人匹配</h2>
            <p>
              你只会匹配一次真人对手，之后双方按顺序连续完成下面两个场景。整个正式实验结束后不能再次匹配或更换对手。
            </p>
          </div>
        </div>
        <div className={`completion-banner card ${progress.all_done ? "complete" : ""}`}>
          <div>
            <span>{progress.all_done ? "EXPERIMENT COMPLETE" : "REQUIRED PROGRESS"}</span>
            <b>
              {progress.all_done
                ? "你已完成唯一一次正式真人实验"
                : cannotResume
                  ? "该账号已经使用过真人实验资格，不能再次匹配"
                  : progress.active_match_id
                    ? `固定对手实验进行中：${progress.done_count} / ${progress.required_count} 个场景`
                    : `待完成场景：${progress.done_count} / ${progress.required_count}`}
            </b>
            <small>一次匹配 · 同一对手 · 两个场景连续完成 · 不允许重复参加</small>
          </div>
          <strong>
            {progress.done_count}/{progress.required_count}
          </strong>
        </div>
        <div className="scene-grid">
          {progress.scenes.map((s) => {
            const isFirstRequired = s.scene_key === firstRequiredScene?.scene_key;
            const canEnter = isFirstRequired && !progress.all_done && !cannotResume;
            return (
            <article
              key={s.scene_key}
              className={`scenario-card card ${s.completed || progress.all_done ? "completed" : ""}`}
              data-no={s.no}
            >
              <span className="scenario-status">
                {s.completed
                  ? "✓ 已完成"
                  : progress.all_done
                    ? "✓ 实验已结束"
                    : isFirstRequired
                      ? progress.active_match_id
                        ? "● 点击继续当前实验"
                        : "① 从此场景开始"
                      : "② 与同一对手自动进入"}
              </span>
              <h3>{s.title}</h3>
              <p>{s.short_desc}</p>
              <div className="scenario-meta">
                <i>{progress.rounds_per_scene} 轮</i>
                <i>真人同步</i>
                <i>{s.completed ? `得分 ${s.best_score}` : "A / B"}</i>
              </div>
              <button
                className="primary"
                type="button"
                disabled={busy || !canEnter}
                onClick={() => startPvp(s)}
              >
                {progress.all_done
                  ? "正式实验已完成"
                  : cannotResume
                    ? "真人实验资格已使用"
                    : isFirstRequired
                      ? progress.active_match_id
                        ? "继续当前实验 →"
                        : "开始唯一一次匹配 →"
                      : "完成第一场景后自动进入"}
              </button>
            </article>
            );
          })}
        </div>
      </div>
    );
  }

  if (stage === "matching" && pvp) {
    const spinDeg = ((waitSec % 12) / 12) * 360;
    return (
      <div className="page page-soft-in">
        <section className="hero card matchmaking-hero">
          <div>
            <div className="eyebrow">MATCHMAKING</div>
            <h2>
              正在匹配真人对手
              <span className="match-dots" aria-hidden>
                <i /><i /><i />
              </span>
            </h2>
            <p>
              场景：{scene?.title || pvp.scene_title}。请保持页面打开，匹配成功后将自动进入第 1
              轮（每轮 15 秒）。
            </p>
            <div className="match-meta">
              <span>
                已等待 <b>{waitSec}</b> 秒
              </span>
              <span>同步限时 · 15 秒/轮</span>
            </div>
          </div>
          <div
            className="ring match-search-ring"
            style={{ ["--p" as string]: `${spinDeg}deg` }}
            aria-label="正在搜索对手"
          >
            <b>搜</b>
          </div>
        </section>
        <div className="match-pulse-bar" aria-hidden>
          <i />
        </div>
        <div className="rule-actions">
          <small>队列中仅匹配同一场景的在线参与者</small>
          <button className="secondary" type="button" onClick={() => cancelMatching()}>
            取消匹配
          </button>
        </div>
      </div>
    );
  }

  if (stage === "matched" && pvp) {
    return (
      <div className="page page-soft-in">
        <section className="hero card match-found-hero">
          <div>
            <div className="eyebrow">MATCH FOUND</div>
            <h2>匹配成功</h2>
            <p>
              对手 <b>{pvp.opponent_nickname || "参与者"}</b> 已就位，即将开始第 1 轮…
            </p>
          </div>
          <div className="ring match-found-ring" style={{ ["--p" as string]: "360deg" }}>
            <b>✓</b>
          </div>
        </section>
      </div>
    );
  }

  if (stage === "pvp" && scene && pvp) {
    if (pvp.status === "finished") {
      return (
        <div className="page page-soft-in">
          <section className="finish card">
            <div className="trophy">✦</div>
            <div className="eyebrow" style={{ justifyContent: "center", marginTop: 20 }}>
              真人匹配对局结束
            </div>
            <h2>
              {scene.title} · vs {pvp.opponent_nickname || "对手"}
            </h2>
            <div className="finish-score">{pvp.my_score} 分</div>
            <p>对方得分：{pvp.opponent_score}</p>
            <p>你已与同一位对手完成全部两个场景。本次正式实验机会已经使用，不能再次匹配或更换对手重做。</p>
            <div className="finish-actions">
              <button
                className="primary"
                type="button"
                onClick={() => {
                  setPvp(null);
                  setStage("scenes");
                }}
              >
                查看实验完成情况
              </button>
            </div>
          </section>
        </div>
      );
    }

    const history = [...pvp.history].reverse();
    const waitingResult = pvp.i_have_chosen && !pvp.opponent_has_chosen;
    const timeoutSec = pvp.round_timeout_sec || 15;
    const urgent = secondsLeft <= 5 && !pvp.i_have_chosen;
    const ringDeg = Math.max(0, Math.min(360, (secondsLeft / timeoutSec) * 360));

    return (
      <div className="page">
        <section className={`round-card card ${urgent ? "round-urgent" : ""}`}>
          <div className="roundtop">
            <div>
              <div className="eyebrow">真人对战 · {pvp.opponent_nickname || "对手"}</div>
              <h2>第 {pvp.current_round} 轮</h2>
              <p>
                双方同步选择。超时未选本轮得 0 分
                {pvp.opponent_has_chosen && !pvp.i_have_chosen ? "；对方已提交，正等你选择。" : "。"}
              </p>
            </div>
            <div
              className={`ring timer-ring ${urgent ? "urgent" : ""}`}
              style={{ ["--p" as string]: `${ringDeg}deg` }}
              aria-live="polite"
              aria-label={`剩余 ${secondsLeft} 秒`}
            >
              <b>{secondsLeft}</b>
              <small>秒</small>
            </div>
          </div>

          <div
            className="roundbar"
            style={{ gridTemplateColumns: `repeat(${pvp.rounds_total}, 1fr)` }}
          >
            {Array.from({ length: pvp.rounds_total }, (_, i) => {
              const n = i + 1;
              const cls =
                n < pvp.current_round ? "done" : n === pvp.current_round ? "now" : "";
              return <i key={n} className={cls} />;
            })}
          </div>

          <div className="timer-track" aria-hidden>
            <i
              style={{
                width: `${Math.max(0, Math.min(100, (secondsLeft / timeoutSec) * 100))}%`,
              }}
              className={urgent ? "urgent" : ""}
            />
          </div>

          <div className="scoreboard">
            <div className="scorebox">
              <span>你的累计得分</span>
              <b key={`me-${pvp.my_score}`} className="score-bump">
                {pvp.my_score}
              </b>
            </div>
            <div className="versus">VS</div>
            <div className="scorebox">
              <span>{pvp.opponent_nickname || "对方"}</span>
              <b key={`op-${pvp.opponent_score}`} className="score-bump">
                {pvp.opponent_score}
              </b>
            </div>
          </div>

          {history[0] && (
            <div className="last-result result-flash" key={history[0].round_no}>
              上一轮：你 <b>{history[0].my_timed_out ? "超时" : history[0].my_choice}</b>，对方{" "}
              <b>{history[0].opponent_timed_out ? "超时" : history[0].opponent_choice}</b>
              。你得 <b>{history[0].my_points}</b>，对方得 <b>{history[0].opponent_points}</b>。
            </div>
          )}

          {pvp.i_have_chosen ? (
            <div className={`choice-title wait-status ${waitingResult ? "pulse" : ""}`}>
              {waitingResult ? "已提交，等待对方选择或倒计时结束…" : "正在结算本轮…"}
            </div>
          ) : (
            <>
              <div className="choice-title">
                {urgent ? "时间将尽，请尽快选择" : "请选择本轮行动"}
              </div>
              <div className="choice-buttons">
                <button
                  className="choice-btn"
                  type="button"
                  disabled={busy || secondsLeft <= 0}
                  onClick={() => playPvp("A")}
                >
                  <b>A · {scene.option_a}</b>
                  <span>{scene.option_a_text}</span>
                </button>
                <button
                  className="choice-btn"
                  type="button"
                  disabled={busy || secondsLeft <= 0}
                  onClick={() => playPvp("B")}
                >
                  <b>B · {scene.option_b}</b>
                  <span>{scene.option_b_text}</span>
                </button>
              </div>
            </>
          )}
        </section>
        {history.length > 0 && (
          <section className="history-card card">
            <div className="history-title">之前轮次</div>
            <div className="history-row head">
              <span>轮次</span>
              <span>你</span>
              <span>对方</span>
              <span>你得分</span>
              <span>对方得分</span>
            </div>
            {history.map((h) => (
              <div className="history-row" key={h.round_no}>
                <span>{h.round_no}</span>
                <span>{h.my_timed_out ? "超时" : h.my_choice}</span>
                <span>{h.opponent_timed_out ? "超时" : h.opponent_choice}</span>
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

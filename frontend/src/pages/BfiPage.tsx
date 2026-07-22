import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "../api/client";
import * as surveyApi from "../api/survey";
import type { MyResponse, SurveyInstrument } from "../api/survey";
import { useDemo } from "../context/DemoContext";
import { useToast } from "../context/ToastContext";
import { useSiteContent } from "../hooks/useSite";

const PAGE_SIZE = 11;

function focusQuestion(itemNo: number, flash = true) {
  const el = document.querySelector(`[data-item-no="${itemNo}"]`);
  if (!(el instanceof HTMLElement)) return;
  el.scrollIntoView({ behavior: "smooth", block: "start" });
  if (!flash) return;
  el.classList.remove("qrow-flash");
  // 强制重启动画
  void el.offsetWidth;
  el.classList.add("qrow-flash");
  window.setTimeout(() => el.classList.remove("qrow-flash"), 900);
}

export function BfiPage() {
  const { toast } = useToast();
  const { demoMode, getMyResponse, saveAnswers, submitSurvey } = useDemo();
  const { byKey: content } = useSiteContent();
  const [introDone, setIntroDone] = useState(false);
  const [instrument, setInstrument] = useState<SurveyInstrument | null>(null);
  const [mine, setMine] = useState<MyResponse | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [attentionAnswers, setAttentionAnswers] = useState<Record<string, number>>({});
  const [diligenceAnswers, setDiligenceAnswers] = useState<Record<string, number>>({});
  const [qpage, setQpage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  /** 翻页后定位到某题；null 表示不处理 */
  const pendingFocusItem = useRef<number | null>(null);
  const pageTimings = useRef<Record<string, number>>({});
  const pageStartedAt = useRef(Date.now());
  const blurCount = useRef(0);

  function recordCurrentPageTime() {
    if (!introDone) return;
    const elapsed = Math.max((Date.now() - pageStartedAt.current) / 1000, 0);
    const key = String(qpage);
    pageTimings.current[key] = (pageTimings.current[key] || 0) + elapsed;
    pageStartedAt.current = Date.now();
  }

  useEffect(() => {
    if (!introDone || mine?.status === "submitted") return;
    pageStartedAt.current = Date.now();
    const onVisibility = () => {
      if (document.visibilityState === "hidden") blurCount.current += 1;
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [introDone, mine?.status]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [inst, resp] = await Promise.all([
          surveyApi.getBfi(),
          demoMode ? getMyResponse() : surveyApi.getMyResponse(),
        ]);
        if (cancelled) return;
        setInstrument(inst);
        setMine(resp);
        const map: Record<number, number> = {};
        Object.entries(resp.answers).forEach(([k, v]) => {
          map[Number(k)] = v;
        });
        setAnswers(map);
        if (resp.status === "submitted" || resp.answered_count > 0) setIntroDone(true);
      } catch (e) {
        toast(e instanceof ApiError ? e.message : "加载问卷失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [toast, demoMode, getMyResponse]);

  const answered = Object.keys(answers).length;
  const progress = Math.round((answered / 44) * 100);
  const start = (qpage - 1) * PAGE_SIZE;
  const pageItems = useMemo(
    () => instrument?.items.slice(start, start + PAGE_SIZE) ?? [],
    [instrument, start],
  );
  const groupProgress = useMemo(() => {
    return [1, 2, 3, 4].map((g) => {
      const from = (g - 1) * PAGE_SIZE + 1;
      const to = g * PAGE_SIZE;
      let done = 0;
      for (let n = from; n <= to; n += 1) {
        if (answers[n]) done += 1;
      }
      return { group: g, done, total: PAGE_SIZE, from, to };
    });
  }, [answers]);
  const pageDone = pageItems.filter((item) => answers[item.item_no]).length;

  function jumpToUnanswered() {
    const allItems = instrument?.items ?? [];
    const first = allItems.find((item) => !answers[item.item_no]);
    if (!first) {
      toast("全部题目已作答");
      return;
    }
    const targetPage = Math.ceil(first.item_no / PAGE_SIZE);
    toast(`已定位到第 ${first.item_no} 题`);
    goPage(targetPage, { skipCheck: true, focusItemNo: first.item_no });
  }

  async function onAnswer(itemNo: number, value: number) {
    setAnswers((prev) => ({ ...prev, [itemNo]: value }));
    try {
      const resp = demoMode
        ? await saveAnswers([{ item_no: itemNo, value }])
        : await surveyApi.saveAnswers([{ item_no: itemNo, value }]);
      setMine(resp);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "保存失败");
    }
  }

  function goPage(next: number, opts?: { skipCheck?: boolean; focusItemNo?: number }) {
    if (!opts?.skipCheck && next > qpage) {
      const unanswered = pageItems.find((item) => !answers[item.item_no]);
      if (unanswered) {
        toast(`本组还有未作答题目（第 ${unanswered.item_no} 题）`);
        focusQuestion(unanswered.item_no);
        return;
      }
    }
    // 等新一组题目渲染后再滚到目标题（默认本组第一题）
    const startNo = (next - 1) * PAGE_SIZE + 1;
    const focusNo = opts?.focusItemNo ?? startNo;
    if (next === qpage) {
      window.setTimeout(() => focusQuestion(focusNo), 40);
      return;
    }
    pendingFocusItem.current = focusNo;
    setQpage(next);
  }

  useEffect(() => {
    const itemNo = pendingFocusItem.current;
    if (itemNo == null) return;
    const timer = window.setTimeout(() => {
      pendingFocusItem.current = null;
      focusQuestion(itemNo);
    }, 60);
    return () => window.clearTimeout(timer);
  }, [qpage, pageItems]);

  async function onSubmit() {
    if (answered < 44) {
      const allItems = instrument?.items ?? [];
      const first = allItems.find((item) => !answers[item.item_no]);
      if (first) {
        const targetPage = Math.ceil(first.item_no / PAGE_SIZE);
        toast(`还有 ${44 - answered} 题未完成，已定位到第 ${first.item_no} 题`);
        goPage(targetPage, { skipCheck: true, focusItemNo: first.item_no });
      } else {
        toast(`还有 ${44 - answered} 题未完成，请检查后提交`);
      }
      return;
    }
    recordCurrentPageTime();
    const qualityChecks = instrument?.quality_checks ?? [];
    const missingCheck = qualityChecks.find((check) => !attentionAnswers[check.check_id]);
    if (missingCheck) {
      toast("请先完成页面下方的作答确认题");
      document
        .querySelector(`[data-quality-check="${missingCheck.check_id}"]`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    const diligenceChecks = ["diligence_read", "diligence_authentic", "diligence_technical"];
    if (diligenceChecks.some((checkId) => !diligenceAnswers[checkId])) {
      toast("请完成作答质量确认后再提交");
      document.querySelector("[data-diligence-check]")?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
      return;
    }
    const confirmed = window.confirm(
      demoMode
        ? "演示提交仅保存在临时内存中，不会写入正式库，也不会进入 CSV。可随时重置后重做。\n\n确定提交演示问卷吗？"
        : "人格问卷正式提交后只有一次机会，不能自行修改或重做。请确认你已认真、如实完成全部题目。\n\n确定正式提交吗？",
    );
    if (!confirmed) return;
    setBusy(true);
    try {
      recordCurrentPageTime();
      const telemetry = {
        diligence_answers: diligenceAnswers,
        page_timings_seconds: pageTimings.current,
        blur_count: blurCount.current,
      };
      const resp = demoMode
        ? await submitSurvey(attentionAnswers, telemetry, answers)
        : await surveyApi.submitSurvey(attentionAnswers, telemetry);
      setMine(resp);
      toast(
        demoMode
          ? "演示问卷已提交，可进入博弈演示（数据不保存）"
          : resp.unlock_games
            ? "问卷已提交，博弈入口已解锁"
            : "问卷已提交，本次答卷未进入真人博弈样本",
      );
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "提交失败");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <div className="page"><p>加载中…</p></div>;

  if (mine?.status === "submitted" && mine.feedback_unlocked && mine.personality) {
    const p = mine.personality;
    const dims = [
      `开放性 ${Math.round(p.o * 20)}`,
      `尽责性 ${Math.round(p.c * 20)}`,
      `外向性 ${Math.round(p.e * 20)}`,
      `宜人性 ${Math.round(p.a * 20)}`,
      `情绪敏感 ${Math.round(p.n * 20)}`,
    ];
    return (
      <div className="page">
        <section className="hero card">
          <div>
            <div className="eyebrow">
              {demoMode ? "演示反馈 · 数据不保存" : "实验已完成 · 人格反馈"}
            </div>
            <h2>你的人格轮廓已生成</h2>
            <p>
              {p.summary_label}。
              {demoMode
                ? "这是演示结果，可点顶部「重置演示」后重做。"
                : "结果用于解释博弈中的决策倾向，不代表能力高低。"}
            </p>
          </div>
          <div className="ring" style={{ ["--p" as string]: "360deg" }}>
            <b>100%</b>
          </div>
        </section>
        <div className="statgrid" style={{ marginTop: 18 }}>
          {dims.map((x) => (
            <div className="stat card" key={x}>
              <span>人格维度</span>
              <b>{x}</b>
              <em>已生成</em>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (mine?.status === "submitted") {
    const eligible = mine.unlock_games;
    return (
      <div className="page">
        <section className="hero card">
          <div>
            <div className="eyebrow">
              {eligible ? "问卷已提交 · 等待实验完成" : "问卷已提交 · 流程结束"}
            </div>
            <h2>{eligible ? "人格反馈将在博弈结束后展示" : "本次答卷未进入真人博弈样本"}</h2>
            <p>
              {eligible
                ? "你的答案已经安全记录。为避免人格标签影响后续决策，请先完成全部必做博弈场景；完成后回到这里即可查看结果。"
                : "你的答案已经安全记录，但未达到本次真人对决的数据质量要求，因此不会进入匹配。如作答时遇到技术故障，请联系实验管理员。"}
            </p>
          </div>
          <div className="ring" style={{ ["--p" as string]: "360deg" }}>
            <b>✓</b>
          </div>
        </section>
        <div className="quality">
          <i>→</i>
          <div>
            <b>{eligible ? "下一步：进入博弈实验" : "本次实验流程已结束"}</b>
            <small>
              {eligible
                ? "只有双方问卷质量均通过，才会进入真人匹配。"
                : "正式答卷不能覆盖或重新提交；技术故障由实验管理员核查处理。"}
            </small>
          </div>
        </div>
      </div>
    );
  }

  if (!introDone) {
    const intro = content["bfi.intro"];
    const introTitle = intro?.title?.trim() || "BFI-44 人格问卷";
    const introParts = (intro?.body || "").split("\n\n").map((p) => p.trim()).filter(Boolean);
    // CMS 里若仍是「请先阅读以下介绍」这类空话，改用内置说明
    const vague =
      !introParts.length ||
      introParts.some((p) => p.includes("请先阅读以下") && introParts.length <= 2);
    const introLead = vague
      ? "本问卷共 44 题，用于了解你在五个方面的稳定倾向。作答约需 6–8 分钟，请按真实、日常的自己选择，而不是理想中的自己。"
      : introParts[0];
    const introNote =
      introParts.length > 1 && !vague
        ? introParts[introParts.length - 1]
        : "人格没有好坏之分。结果仅用于本次实验中的行为分析，不作为临床诊断。";
    const announcement = content["announcement.banner"];
    const dimensions = [
      { code: "O", name: "开放性", en: "Openness", desc: "好奇、想象与接受新想法的程度" },
      { code: "C", name: "尽责性", en: "Conscientiousness", desc: "条理、可靠与坚持完成任务的程度" },
      { code: "E", name: "外向性", en: "Extraversion", desc: "活力、社交与主动表达的程度" },
      { code: "A", name: "宜人性", en: "Agreeableness", desc: "信任、合作与体谅他人的程度" },
      { code: "N", name: "情绪敏感", en: "Neuroticism", desc: "紧张、忧虑与情绪起伏的敏感程度" },
    ];

    return (
      <div className="page theory-page">
        {announcement?.body?.trim() && (
          <div className="alert" style={{ marginBottom: 16 }}>
            <i>!</i>
            <div>
              <b>{announcement.title || "平台公告"}</b>
              <small>{announcement.body}</small>
            </div>
          </div>
        )}
        <section className="theory-hero card">
          <div>
            <div className="eyebrow">BFI-44 · 问卷入口</div>
            <h2>{introTitle}</h2>
            <p>{introLead}</p>
          </div>
        </section>

        <div className="alert" role="alert" style={{ marginTop: 16, marginBottom: 16 }}>
          <i>!</i>
          <div>
            <b>请注意：正式人格检测只有一次机会</b>
            <small>
              为保证问卷质量，每位参与者只有一次正式检测机会，请大家仔细、如实作答哦～提交后不能自行修改或重做；如遇技术故障，请联系管理员核实处理。
            </small>
          </div>
        </div>

        <div className="dimension-grid">
          {dimensions.map((d, i) => (
            <article
              className="dimension-card card"
              key={d.code}
              style={{ animationDelay: `${i * 55}ms` }}
            >
              <i>{d.code}</i>
              <h3>{d.name}</h3>
              <span>{d.en}</span>
              <p>{d.desc}</p>
            </article>
          ))}
        </div>

        <div className="theory-note">
          <b>作答说明</b>
          <span>{introNote}</span>
        </div>
        <div className="theory-action card">
          <div>
            <small>预计用时</small>
            <b>6–8 分钟 · 共 44 题</b>
          </div>
          <button className="primary" type="button" onClick={() => setIntroDone(true)}>
            我已知晓，开始作答 →
          </button>
        </div>
      </div>
    );
  }

  const surveyHero = content["bfi.survey_hero"];
  const scaleLabels = [
    ["1", "非常不同意"],
    ["2", "比较不同意"],
    ["3", "中立"],
    ["4", "比较同意"],
    ["5", "非常同意"],
  ] as const;

  function renderScale(
    name: string,
    value: number | undefined,
    onPick: (v: number) => void,
  ) {
    return (
      <div className="bfi-scale" role="radiogroup" aria-label="符合程度">
        {[1, 2, 3, 4, 5].map((v) => (
          <label key={v} className={value === v ? "picked" : undefined} title={scaleLabels[v - 1][1]}>
            <input
              type="radio"
              name={name}
              checked={value === v}
              onChange={() => onPick(v)}
            />
            <span className="bfi-scale-cell">{v}</span>
          </label>
        ))}
      </div>
    );
  }

  return (
    <div className="page bfi-survey-page">
      <header className="bfi-toolbar card">
        <div className="bfi-toolbar-main">
          <div>
            <div className="eyebrow">BFI-44 · 人格问卷</div>
            <h2>{surveyHero?.title || "请判断以下描述与你的符合程度"}</h2>
          </div>
          <span className="bfi-autosave">自动保存</span>
        </div>
        <div className="bfi-toolbar-meta">
          <span>
            第 {qpage} 组 / 共 4 组
          </span>
          <div className="bfi-progress-track" aria-hidden>
            <i style={{ width: `${progress}%` }} />
          </div>
          <b>
            {answered} / 44
          </b>
        </div>
        <p className="bfi-toolbar-hint">
          {surveyHero?.body ||
            "请根据真实、稳定的自己作答。1 = 非常不同意，5 = 非常同意。答案会自动保存。"}
        </p>
      </header>

      <div className="bfi-layout">
        <section className="bfi-panel card">
          <div className="bfi-matrix-head" aria-hidden>
            <span className="bfi-matrix-stem-label">题目</span>
            <div className="bfi-matrix-scale-labels">
              {scaleLabels.map(([n, label]) => (
                <span key={n}>
                  <b>{n}</b>
                  {label}
                </span>
              ))}
            </div>
          </div>

          <div key={qpage} className="qpage-anim bfi-matrix">
            {pageItems.map((item) => (
              <div
                className={`bfi-qrow${answers[item.item_no] ? " answered" : ""}`}
                key={item.item_no}
                data-item-no={item.item_no}
              >
                <div className="bfi-qtext">
                  <b>{String(item.item_no).padStart(2, "0")}</b>
                  <span>我认为自己是一个{item.stem}的人。</span>
                </div>
                {renderScale(`q${item.item_no}`, answers[item.item_no], (v) =>
                  onAnswer(item.item_no, v),
                )}
              </div>
            ))}

            {qpage === 4 && (instrument?.quality_checks.length ?? 0) > 0 ? (
              <div className="quality-check-block">
                <div className="quality-check-heading">
                  <b>作答确认</b>
                  <span>以下题目不计入人格得分，请按题目中的要求选择。</span>
                </div>
                {instrument?.quality_checks.map((check, index) => (
                  <div
                    className={`bfi-qrow${attentionAnswers[check.check_id] ? " answered" : ""}`}
                    key={check.check_id}
                    data-quality-check={check.check_id}
                  >
                    <div className="bfi-qtext">
                      <b>C{index + 1}</b>
                      <span>{check.stem}</span>
                    </div>
                    {renderScale(check.check_id, attentionAnswers[check.check_id], (v) =>
                      setAttentionAnswers((previous) => ({
                        ...previous,
                        [check.check_id]: v,
                      })),
                    )}
                  </div>
                ))}
              </div>
            ) : null}

            {qpage === 4 ? (
              <div className="quality-check-block" data-diligence-check>
                <div className="quality-check-heading">
                  <b>作答质量确认</b>
                  <span>以下内容不计入人格得分，仅用于数据质量复核。</span>
                </div>
                {[
                  ["diligence_read", "我认真阅读了每道题，并根据题意作答。"],
                  ["diligence_authentic", "我的回答能够反映日常、稳定的自己。"],
                  ["diligence_technical", "本次作答存在明显技术问题，影响了我的回答。"],
                ].map(([checkId, stem], index) => (
                  <div
                    className={`bfi-qrow${diligenceAnswers[checkId] ? " answered" : ""}`}
                    key={checkId}
                  >
                    <div className="bfi-qtext">
                      <b>S{index + 1}</b>
                      <span>{stem}</span>
                    </div>
                    {renderScale(checkId, diligenceAnswers[checkId], (v) =>
                      setDiligenceAnswers((previous) => ({
                        ...previous,
                        [checkId]: v,
                      })),
                    )}
                  </div>
                ))}
              </div>
            ) : null}
          </div>

          <div className="qfoot bfi-qfoot">
            <button
              className="secondary"
              type="button"
              disabled={qpage === 1}
              onClick={() => goPage(Math.max(1, qpage - 1))}
            >
              ← 上一组
            </button>
            <span>
              本组 {pageDone}/{PAGE_SIZE}
            </span>
            {qpage < 4 ? (
              <button className="primary" type="button" onClick={() => goPage(qpage + 1)}>
                下一组 →
              </button>
            ) : (
              <button className="primary" type="button" disabled={busy} onClick={onSubmit}>
                {busy ? "提交中…" : answered < 44 ? `还差 ${44 - answered} 题` : "提交问卷 →"}
              </button>
            )}
          </div>
        </section>

        <aside className="bfi-side card">
          <div className="bfi-side-title">答题进度</div>
          <div className="bfi-side-total">
            <b>{answered} / 44</b>
            <span>{progress}%</span>
          </div>
          <div className="bfi-side-ring-wrap" aria-hidden>
            <div className="ring" style={{ ["--p" as string]: `${progress * 3.6}deg` }}>
              <b>{progress}%</b>
            </div>
          </div>
          <ul className="bfi-side-groups">
            {groupProgress.map((g) => (
              <li key={g.group} className={g.group === qpage ? "current" : g.done === g.total ? "done" : ""}>
                <button type="button" onClick={() => goPage(g.group, { skipCheck: g.group < qpage })}>
                  <span>
                    第 {g.group} 组
                    {g.group === qpage ? " · 当前" : ""}
                  </span>
                  <b>
                    {g.done}/{g.total}
                  </b>
                </button>
              </li>
            ))}
          </ul>
          <button className="secondary bfi-side-jump" type="button" onClick={jumpToUnanswered}>
            定位未答题
          </button>
        </aside>
      </div>
    </div>
  );
}

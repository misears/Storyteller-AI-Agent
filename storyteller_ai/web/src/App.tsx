import { FormEvent, useEffect, useRef, useState } from "react";
import { BookOpen, Dice5, Library, MessageSquare, Plus, Save, Send, Settings2, Sparkles, X } from "lucide-react";

type Campaign = { id: string; title: string; status: string; mode: string; ruleset_id: string; setting_pack_id: string };
type ChatMessage = { id: string; speaker_kind: string; content: string; seq: number };
type Ruleset = { id: string; name: string; version: string; mechanic?: string };
type Bible = { premise: string; pitch_for_players: string; themes: string[]; opening_situation: string };
type Sheet = { sheet_id: string; name: string; template_key: string; version?: number; fields?: Record<string, string | number>; field_schema?: { name: string; label?: string; type?: string }[] };
type ActiveTurnRequest = { campaignId: string; clientMsgId: string; startedAt: number };
type AISetupState = {
  provider: "ollama" | "openai" | "anthropic";
  model: string;
  ollama_mode: "auto" | "cpu";
  running: boolean;
  url: string | null;
  managed: boolean;
  models: { name: string; size?: number }[];
  credentials: { openai: boolean; anthropic: boolean };
};
type ModelPullJob = { id: string; model: string; status: string; progress?: string; completed: number; total: number | null; error?: string | null };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!response.ok) {
    const body = await response.text();
    let message = body;
    try {
      const detail = (JSON.parse(body) as { detail?: unknown }).detail;
      if (typeof detail === "string") message = detail;
    } catch { /* Keep plain-text API errors as-is. */ }
    throw new Error(message);
  }
  return response.json();
}

export function App() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [rulesets, setRulesets] = useState<Ruleset[]>([]);
  const [selected, setSelected] = useState<Campaign | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [notice, setNotice] = useState("Select a chronicle to begin.");
  const [loading, setLoading] = useState(false);
  const [turnElapsed, setTurnElapsed] = useState(0);
  const [showSetup, setShowSetup] = useState(false);
  const [bible, setBible] = useState<Bible | null>(null);
  const [utility, setUtility] = useState<"packs" | "saves" | "sheets" | "documents" | "profiles" | "ai" | null>(null);
  const [utilityItems, setUtilityItems] = useState<unknown[]>([]);
  const [activeSheet, setActiveSheet] = useState<Sheet | null>(null);
  const [aiSetup, setAiSetup] = useState<AISetupState | null>(null);
  const [aiKey, setAiKey] = useState("");
  const [modelToPull, setModelToPull] = useState("");
  const [pullJob, setPullJob] = useState<ModelPullJob | null>(null);
  const activeTurnRef = useRef<ActiveTurnRequest | null>(null);
  const retryActionRef = useRef<{ content: string; clientMsgId: string } | null>(null);

  async function refresh() {
    const [campaignData, rulesetData] = await Promise.all([
      api<Campaign[]>("/campaigns/"), api<Ruleset[]>("/rulesets")
    ]);
    setCampaigns(campaignData); setRulesets(rulesetData);
  }
  useEffect(() => { refresh().catch((error) => setNotice(error.message)); }, []);

  useEffect(() => {
    if (!loading || !activeTurnRef.current) return;
    const timer = window.setInterval(() => {
      const activeTurn = activeTurnRef.current;
      if (activeTurn) setTurnElapsed(Math.floor((Date.now() - activeTurn.startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [loading]);

  useEffect(() => {
    if (!selected) return;
    const stream = new EventSource(`/campaigns/${selected.id}/stream?last_event_id=0&viewer=player`);
    stream.addEventListener("message.posted", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as Partial<ChatMessage>;
      if (payload.content && payload.id) {
        setMessages((current) => current.some((message) => message.id === payload.id) ? current : [...current, payload as ChatMessage]);
      }
    });
    stream.onerror = () => setNotice("Live stream reconnecting...");
    return () => stream.close();
  }, [selected?.id]);

  async function openCampaign(campaign: Campaign) {
    setSelected(campaign); setNotice("Loading the latest table state...");
    const page = await api<{ messages: ChatMessage[] }>(`/campaigns/${campaign.id}/chat`);
    setMessages(page.messages); setNotice(`${campaign.title || "Untitled chronicle"} is ready.`);
  }

  async function createCampaign(event: FormEvent) {
    event.preventDefault(); setLoading(true);
    try {
      const campaign = await api<Campaign>("/campaigns/", { method: "POST", body: JSON.stringify({ title: newTitle || "Untitled chronicle" }) });
      setNewTitle(""); await refresh(); await openCampaign(campaign);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Could not create campaign"); }
    finally { setLoading(false); }
  }

  async function sendTurn(event: FormEvent) {
    event.preventDefault(); if (!selected || !draft.trim()) return;
    const content = draft.trim();
    const clientMsgId = retryActionRef.current?.content === content
      ? retryActionRef.current.clientMsgId
      : crypto.randomUUID();
    retryActionRef.current = { content, clientMsgId };
    activeTurnRef.current = { campaignId: selected.id, clientMsgId, startedAt: Date.now() };
    setTurnElapsed(0); setLoading(true); setNotice("Storyteller is generating a response...");
    try {
      const result = await api<{ text: string; status?: string }>(`/campaigns/${selected.id}/turns`, {
        method: "POST",
        body: JSON.stringify({ content, client_msg_id: clientMsgId }),
      });
      if (result.status === "cancelled") {
        setNotice("Generation cancelled. Your action is still here and can be retried.");
        return;
      }
      const page = await api<{ messages: ChatMessage[] }>(`/campaigns/${selected.id}/chat`);
      setMessages(page.messages); setDraft(""); retryActionRef.current = null;
      setNotice(result.text ? "The Storyteller has answered." : "Turn resolved.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Turn failed. Your action is still here and can be retried.");
    } finally {
      activeTurnRef.current = null; setTurnElapsed(0); setLoading(false);
    }
  }

  async function cancelTurn() {
    const activeTurn = activeTurnRef.current;
    if (!activeTurn) return;
    setNotice("Requesting generation cancellation...");
    try {
      const result = await api<{ cancelled: boolean }>(
        `/campaigns/${activeTurn.campaignId}/turns/${activeTurn.clientMsgId}/cancel`,
        { method: "POST" },
      );
      setNotice(result.cancelled
        ? "Cancellation requested. Your action will remain available to retry."
        : "The turn is already saving its response; waiting for it to finish.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not cancel generation.");
    }
  }

  async function saveChronicle() {
    if (!selected) return;
    try {
      await api(`/campaigns/${selected.id}/saves`, { method: "POST", body: JSON.stringify({ name: `Save ${new Date().toLocaleTimeString()}` }) });
      setNotice("Chronicle saved.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Save failed"); }
  }

  async function loadSave(saveId: string) {
    if (!selected) return;
    try {
      await api(`/campaigns/${selected.id}/saves/${saveId}/load`, { method: "POST" });
      const campaign = await api<Campaign>(`/campaigns/${selected.id}`);
      await openCampaign(campaign);
      setUtility(null);
      setNotice("Save loaded as a new timeline.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Could not load save"); }
  }

  async function rollServerDice() {
    if (!selected) return;
    try {
      const roll = await api<{ total?: number; successes?: number }>(`/campaigns/${selected.id}/dice`, { method: "POST", body: JSON.stringify({ expression: "1d20", reason: "player quick roll" }) });
      setNotice(`Server roll recorded${roll.total === undefined ? "" : `: ${roll.total}`}.`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Roll failed"); }
  }

  async function prepareSession() {
    if (!selected) return;
    try {
      await api(`/campaigns/${selected.id}/session-zero/bible`, { method: "POST" });
        const result = await api<{ bible: Bible }>(`/campaigns/${selected.id}/session-zero/bible`);
        setBible(result.bible); 
        setShowSetup(true); 
        setNotice("Review the session-zero bible before opening the table.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Setup failed"); }
  }

  async function openUtility(kind: "packs" | "saves" | "sheets" | "documents" | "profiles") {
    try {
      const path = kind === "packs" ? "/rulesets" : kind === "saves" ? `/campaigns/${selected?.id}/saves` : kind === "sheets" ? "/character-sheets/" : kind === "documents" ? "/documents/list" : "/settings/llm/profiles";
      const result = await api<unknown>(path);
      const wrapper = result as { saves?: unknown[]; sheets?: unknown[]; documents?: unknown[]; profiles?: Record<string, unknown> };
      const profiles = wrapper.profiles ? Object.entries(wrapper.profiles).map(([role, profile]) => ({ name: role, ...profile as object })) : [];
      setUtilityItems(Array.isArray(result) ? result : (wrapper.saves || wrapper.sheets || wrapper.documents || profiles));
      setUtility(kind);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Could not load panel"); }
  }

  async function openAISetup() {
    try {
      const status = await api<AISetupState>("/settings/ai");
      setAiSetup(status);
      setUtility("ai");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Could not load AI setup"); }
  }

  async function refreshAISetup() {
    const status = await api<AISetupState>("/settings/ai");
    setAiSetup(status);
  }

  async function saveAISetup() {
    if (!aiSetup) return;
    try {
      const status = await api<AISetupState>("/settings/ai", {
        method: "PUT",
        body: JSON.stringify({ provider: aiSetup.provider, model: aiSetup.model, ollama_mode: aiSetup.ollama_mode }),
      });
      setAiSetup(status); setNotice("AI provider settings saved.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Could not save AI settings"); }
  }

  async function saveAIKey() {
    if (!aiSetup || !aiKey.trim()) return;
    const provider = aiSetup.provider;
    if (provider === "ollama") return;
    const secret = aiKey;
    setAiKey("");
    try {
      await api(`/settings/ai/credentials/${provider}`, { method: "PUT", body: JSON.stringify({ api_key: secret }) });
      await refreshAISetup(); setNotice(`${provider} key saved securely.`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Could not save provider key"); }
  }

  async function removeAIKey(provider: "openai" | "anthropic") {
    try {
      await api(`/settings/ai/credentials/${provider}`, { method: "DELETE" });
      await refreshAISetup(); setNotice(`${provider} key removed.`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Could not remove provider key"); }
  }

  async function testAIProvider() {
    try {
      await api("/settings/ai/test", { method: "POST" });
      setNotice("Provider connection test succeeded.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Provider test failed"); }
  }

  async function startModelPull(event: FormEvent) {
    event.preventDefault();
    if (!modelToPull.trim()) return;
    try {
      const job = await api<{ id: string; status: string }>("/settings/ai/models/pull", {
        method: "POST", body: JSON.stringify({ model: modelToPull.trim() }),
      });
      setPullJob({ ...job, model: modelToPull.trim(), completed: 0, total: null });
      setModelToPull("");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Could not start model download"); }
  }

  async function cancelModelPull() {
    if (!pullJob) return;
    try {
      await api(`/settings/ai/models/pull/${pullJob.id}`, { method: "DELETE" });
      setPullJob({ ...pullJob, status: "cancelled", progress: "Download cancelled" });
    } catch (error) { setNotice(error instanceof Error ? error.message : "Could not cancel model download"); }
  }

  useEffect(() => {
    if (!pullJob || !["queued", "pulling"].includes(pullJob.status)) return;
    const timer = window.setInterval(() => {
      api<ModelPullJob>(`/settings/ai/models/pull/${pullJob.id}`)
        .then((job) => { setPullJob(job); if (job.status === "complete") refreshAISetup().catch(() => undefined); })
        .catch((error) => setNotice(error instanceof Error ? error.message : "Could not check model download"));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [pullJob?.id, pullJob?.status]);

  async function openSheet(sheet: Sheet) {
    const result = await api<{ sheet: Sheet }>(`/character-sheets/${sheet.sheet_id}`);
    setActiveSheet(result.sheet);
  }

  async function saveSheet() {
    if (!activeSheet) return;
    const result = await api<{ sheet: Sheet }>(`/character-sheets/${activeSheet.sheet_id}`, { method: "PUT", body: JSON.stringify({ fields: activeSheet.fields, expected_version: activeSheet.version }) });
    setActiveSheet(result.sheet); setNotice("Character sheet saved.");
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Sparkles size={17} /></div><div><strong>STORYTELLER</strong><span>chronicle desk</span></div></div>
      <div className="side-label">YOUR CHRONICLES</div>
      <div className="campaign-list">{campaigns.map((campaign) => <button className={`campaign-item ${selected?.id === campaign.id ? "active" : ""}`} key={campaign.id} onClick={() => openCampaign(campaign)}><span className="campaign-dot" /><span><b>{campaign.title || "Untitled"}</b><small>{campaign.status.replace("_", " ")} · {campaign.mode}</small></span></button>)}</div>
      <form className="new-campaign" onSubmit={createCampaign}><input value={newTitle} onChange={(event) => setNewTitle(event.target.value)} placeholder="Name a new chronicle" /><button title="Create chronicle" disabled={loading}><Plus size={17} /></button></form>
      <div className="sidebar-bottom"><button onClick={() => openUtility("packs")}><Library size={16} /> Pack library</button><button onClick={() => openUtility("documents")}><BookOpen size={16} /> PDF library</button><button onClick={() => openUtility("profiles")}><Settings2 size={16} /> Model profiles</button><button onClick={openAISetup}><Settings2 size={16} /> AI provider setup</button><div className="local-badge"><span /> Local server · private</div></div>
    </aside>
    <main className="workspace">
      <header className="topbar"><div><span className="eyebrow">ACTIVE CHRONICLE</span><h1>{selected?.title || "No chronicle selected"}</h1></div><div className="top-actions"><span className="status-pill"><span /> {selected ? "TABLE OPEN" : "WAITING"}</span><button className="icon-button" title="AI provider setup" onClick={openAISetup}><Settings2 size={17} /></button><button className="icon-button" title="Save chronicle" onClick={saveChronicle} disabled={!selected}><Save size={17} /></button><button className="icon-button" title="Open rulesets" onClick={() => openUtility("packs")}><BookOpen size={17} /></button></div></header>
      <div className="content-grid">
        <section className="play-panel"><div className="scene-strip"><div><span className="eyebrow">CURRENT SCENE</span><h2>{selected ? "The table is waiting for a choice" : "Choose a chronicle"}</h2></div><div className="scene-meta"><span><Dice5 size={15} /> server dice</span><span><MessageSquare size={15} /> {messages.length} messages</span></div></div><div className="chat-log">{selected && messages.length === 0 && <div className="empty-state"><Sparkles size={25} /><p>Your opening scene is waiting.</p><small>Send an action below to begin the chronicle.</small></div>}{messages.map((message) => <article className={`message ${message.speaker_kind}`} key={message.id}><div className="message-label">{message.speaker_kind === "player" ? "YOU" : message.speaker_kind.toUpperCase()}</div><p>{message.content}</p></article>)}</div><form className="turn-composer" onSubmit={sendTurn}><textarea value={draft} onChange={(event) => setDraft(event.target.value)} disabled={!selected || loading} placeholder={selected ? "What do you do?" : "Select a chronicle first"} />{loading ? <div className="turn-progress"><span>Generating · {turnElapsed}s</span><button type="button" className="cancel-turn" onClick={cancelTurn} title="Cancel generation"><X size={16} /> Cancel</button></div> : <button className="send-button" title="Send turn" disabled={!selected || !draft.trim()}><Send size={18} /></button>}</form><div className="notice">{notice}</div></section>
        <aside className="inspector"><div className="inspector-heading"><span className="eyebrow">TABLE CARD</span><Settings2 size={16} /></div><div className="card-rule" /><dl><div><dt>RULESET</dt><dd>{selected?.ruleset_id || "freeform"}</dd></div><div><dt>SETTING</dt><dd>{selected?.setting_pack_id || "default"}</dd></div><div><dt>MODE</dt><dd>{selected?.mode || "group"}</dd></div><div><dt>RULESETS INSTALLED</dt><dd>{rulesets.length || "--"}</dd></div></dl><div className="inspector-block"><span className="eyebrow">QUICK TOOLS</span><button onClick={rollServerDice} disabled={!selected}><Dice5 size={15} /> Roll dice</button><button onClick={saveChronicle} disabled={!selected}><Save size={15} /> Named save</button><button onClick={() => openUtility("saves")} disabled={!selected}><Save size={15} /> Browse saves</button><button onClick={() => openUtility("sheets")}><BookOpen size={15} /> Character sheets</button><button onClick={prepareSession} disabled={!selected}><BookOpen size={15} /> Prepare session</button></div></aside>
      </div>
    </main>
      {showSetup && selected && <div className="setup-overlay"><section className="setup-dialog"><div className="setup-header"><div><span className="eyebrow">SESSION ZERO</span><h2>{selected.title}</h2></div><button className="icon-button" onClick={() => setShowSetup(false)} title="Close setup">×</button></div><div className="setup-progress"><span className="done">01 CHRONICLE BIBLE</span><span>02 PLAYERS</span><span>03 OPENING SCENE</span></div><label>PREMISE<textarea value={bible?.premise || ""} readOnly /></label><label>PLAYER PITCH<textarea value={bible?.pitch_for_players || ""} readOnly /></label><div className="setup-columns"><div><span className="eyebrow">THEMES</span><div className="theme-list">{(bible?.themes || []).map((theme) => <span key={theme}>{theme}</span>)}</div></div><div><span className="eyebrow">OPENING SITUATION</span><p className="setup-opening">{bible?.opening_situation}</p></div></div><div className="setup-footer"><span className="notice">Review is local and saved to the campaign event log.</span><button className="primary-action" onClick={async () => { if (!selected) return; await api(`/campaigns/${selected.id}/session-zero/complete`, { method: "POST" }); setShowSetup(false); setNotice("Session zero complete. The opening scene is ready."); }}>Open the table <Sparkles size={15} /></button></div></section></div>}
      {utility && <div className="setup-overlay"><section className={`utility-dialog ${utility === "ai" ? "ai-dialog" : ""}`}><div className="setup-header"><div><span className="eyebrow">{utility === "ai" ? "AI PROVIDER" : "TABLE LIBRARY"}</span><h2>{utility === "packs" ? "Rulesets" : utility === "saves" ? "Named saves" : utility === "sheets" ? "Character sheets" : utility === "documents" ? "PDF library" : utility === "profiles" ? "Model profiles" : "AI setup"}</h2></div><button className="icon-button" onClick={() => { setUtility(null); setActiveSheet(null); setAiKey(""); }} title="Close panel"><X size={17} /></button></div>{utility === "ai" ? <div className="ai-settings">
        {aiSetup && <>
          {aiSetup.provider === "ollama" && <div className="ai-runtime"><span className={`runtime-light ${aiSetup.running ? "online" : ""}`} /><div><strong>{aiSetup.running ? "Local runtime ready" : "Local runtime stopped"}</strong><small>{aiSetup.running ? `${aiSetup.url}${aiSetup.managed ? " · managed by Storyteller" : " · existing service"}` : "Ollama can be started when local mode is selected."}</small></div></div>}
          <label className="ai-field">Provider<select value={aiSetup.provider} onChange={(event) => { const provider = event.target.value as AISetupState["provider"]; const model = provider === "ollama" ? (aiSetup.models.find((item) => item.name === aiSetup.model)?.name || aiSetup.models.find((item) => item.name === "qwen3:4b-instruct")?.name || aiSetup.models[0]?.name || "qwen3:4b-instruct") : provider === "openai" ? (/^gpt-/i.test(aiSetup.model) ? aiSetup.model : "gpt-4o-mini") : (/^claude-/i.test(aiSetup.model) ? aiSetup.model : "claude-3-5-haiku-latest"); setAiSetup({ ...aiSetup, provider, model }); }}><option value="ollama">Ollama · local</option><option value="openai">OpenAI · cloud</option><option value="anthropic">Anthropic · cloud</option></select></label>
          {aiSetup.provider === "ollama" && <div className="ai-field"><span>Runtime mode</span><div className="segmented"><button className={aiSetup.ollama_mode === "auto" ? "selected" : ""} onClick={() => setAiSetup({ ...aiSetup, ollama_mode: "auto" })}>Auto</button><button className={aiSetup.ollama_mode === "cpu" ? "selected" : ""} onClick={() => setAiSetup({ ...aiSetup, ollama_mode: "cpu" })}>CPU only</button></div><small>Auto reuses an existing Ollama service. CPU only starts an isolated Storyteller process.</small></div>}
          <label className="ai-field">Model{aiSetup.provider === "ollama" ? <select value={aiSetup.model} onChange={(event) => setAiSetup({ ...aiSetup, model: event.target.value })}>{!aiSetup.models.some((model) => model.name === aiSetup.model) && <option value={aiSetup.model}>{aiSetup.model}</option>}{aiSetup.models.map((model) => <option key={model.name} value={model.name}>{model.name}</option>)}</select> : <input value={aiSetup.model} onChange={(event) => setAiSetup({ ...aiSetup, model: event.target.value })} placeholder={aiSetup.provider === "openai" ? "gpt-4o-mini" : "claude-3-5-haiku-latest"} />}</label>
          {aiSetup.provider === "ollama" && <div className="ai-models"><div className="ai-section-title">INSTALLED MODELS <button className="text-action" onClick={() => refreshAISetup().catch((error) => setNotice(error.message))} title="Refresh installed models">Refresh</button></div>{aiSetup.models.length ? aiSetup.models.map((model) => <button className={`model-row ${aiSetup.model === model.name ? "chosen" : ""}`} key={model.name} onClick={() => setAiSetup({ ...aiSetup, model: model.name })}><span>{model.name}</span><small>{model.size ? `${(model.size / 1_000_000_000).toFixed(1)} GB` : "available"}</small></button>) : <p className="ai-hint">No models found on this runtime.</p>}
            <form className="pull-form" onSubmit={startModelPull}><input value={modelToPull} onChange={(event) => setModelToPull(event.target.value)} placeholder="Model name, e.g. qwen3:4b-instruct" aria-label="Model to download" /><button className="primary-action" disabled={!modelToPull.trim()}>Download</button></form>
            {pullJob && <div className="pull-status"><div><span>{pullJob.model}: {pullJob.progress || pullJob.status}</span>{["queued", "pulling"].includes(pullJob.status) && <button className="text-action" onClick={cancelModelPull}>Cancel</button>}</div>{pullJob.total ? <progress value={pullJob.completed} max={pullJob.total} /> : ["queued", "pulling"].includes(pullJob.status) ? <progress /> : null}{pullJob.error && <small>{pullJob.error}</small>}</div>}
          </div>}
          {aiSetup.provider !== "ollama" && <div className="credential-box"><div className="ai-section-title">{aiSetup.provider.toUpperCase()} API KEY <span>{aiSetup.credentials[aiSetup.provider] ? "CONFIGURED" : "NOT SET"}</span></div><form className="pull-form" onSubmit={(event) => { event.preventDefault(); void saveAIKey(); }}><input type="password" autoComplete="new-password" value={aiKey} onChange={(event) => setAiKey(event.target.value)} placeholder="Enter key to replace or add" aria-label={`${aiSetup.provider} API key`} /><button className="primary-action" disabled={!aiKey.trim()}>Save key</button></form><small>Protected with Windows DPAPI. Saved keys cannot be viewed in this app.</small>{aiSetup.credentials[aiSetup.provider] && <button className="text-action remove-key" onClick={() => removeAIKey(aiSetup.provider as "openai" | "anthropic")}>Remove saved key</button>}</div>}
          <div className="ai-actions"><button className="primary-action" onClick={saveAISetup}>Save provider settings</button><button className="secondary-action" onClick={testAIProvider}>Test provider</button></div>
        </>}
      </div> : <><div className="utility-list">{utilityItems.length === 0 && <p className="notice">Nothing saved here yet.</p>}{utilityItems.map((item, index) => { const itemName = (item as Ruleset | Sheet).name || (item as { title?: string; id?: string }).title || (item as { id?: string }).id || "Untitled"; const itemDetail = (item as Ruleset).version || (item as Sheet).template_key || (item as { genres?: string[] }).genres?.join(", ") || "ready"; return utility === "sheets" ? <button className="utility-row" key={index} onClick={() => openSheet(item as Sheet)}><b>{itemName}</b><span>{itemDetail}</span></button> : utility === "saves" ? <button className="utility-row" key={index} onClick={() => loadSave(String((item as { id?: string }).id || ""))}><b>{itemName}</b><span>Load timeline · seq {(item as { event_seq?: number }).event_seq ?? "--"}</span></button> : <div className="utility-row" key={index}><b>{itemName}</b><span>{itemDetail}</span></div>; })}</div>{activeSheet && <div className="sheet-editor"><span className="eyebrow">SHEET V{activeSheet.version || 1}</span>{(activeSheet.field_schema || []).map((field) => <label key={field.name}>{field.label || field.name}<input type={field.type === "number" ? "number" : "text"} value={String(activeSheet.fields?.[field.name] ?? "")} onChange={(event) => setActiveSheet({ ...activeSheet, fields: { ...activeSheet.fields, [field.name]: field.type === "number" ? Number(event.target.value) : event.target.value } })} /></label>)}<button className="primary-action" onClick={saveSheet}>Save sheet <Save size={15} /></button></div>}</>}</section></div>}
  </div>;
}
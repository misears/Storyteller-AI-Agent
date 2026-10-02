import { FormEvent, useEffect, useState } from "react";
import { BookOpen, Dice5, Library, MessageSquare, Plus, Save, Send, Settings2, Sparkles } from "lucide-react";

type Campaign = { id: string; title: string; status: string; mode: string; ruleset_id: string; setting_pack_id: string };
type ChatMessage = { id: string; speaker_kind: string; content: string; seq: number };
type Ruleset = { id: string; name: string; version: string; mechanic?: string };
type Bible = { premise: string; pitch_for_players: string; themes: string[]; opening_situation: string };
type Sheet = { sheet_id: string; name: string; template_key: string; version?: number; fields?: Record<string, string | number>; field_schema?: { name: string; label?: string; type?: string }[] };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!response.ok) throw new Error(await response.text());
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
  const [showSetup, setShowSetup] = useState(false);
  const [bible, setBible] = useState<Bible | null>(null);
  const [utility, setUtility] = useState<"packs" | "saves" | "sheets" | "documents" | "profiles" | null>(null);
  const [utilityItems, setUtilityItems] = useState<unknown[]>([]);
  const [activeSheet, setActiveSheet] = useState<Sheet | null>(null);

  async function refresh() {
    const [campaignData, rulesetData] = await Promise.all([
      api<Campaign[]>("/campaigns/"), api<Ruleset[]>("/rulesets")
    ]);
    setCampaigns(campaignData); setRulesets(rulesetData);
  }
  useEffect(() => { refresh().catch((error) => setNotice(error.message)); }, []);

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
    const content = draft.trim(); setDraft(""); setLoading(true);
    try {
      const result = await api<{ text: string }>(`/campaigns/${selected.id}/turns`, { method: "POST", body: JSON.stringify({ content }) });
      const page = await api<{ messages: ChatMessage[] }>(`/campaigns/${selected.id}/chat`);
      setMessages(page.messages); setNotice(result.text ? "The Storyteller has answered." : "Turn resolved.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Turn failed"); }
    finally { setLoading(false); }
  }

  async function saveChronicle() {
    if (!selected) return;
    try {
      await api(`/campaigns/${selected.id}/saves`, { method: "POST", body: JSON.stringify({ name: `Save ${new Date().toLocaleTimeString()}` }) });
      setNotice("Chronicle saved.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Save failed"); }
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
      <div className="sidebar-bottom"><button onClick={() => openUtility("packs")}><Library size={16} /> Pack library</button><button onClick={() => openUtility("documents")}><BookOpen size={16} /> PDF library</button><button onClick={() => openUtility("profiles")}><Settings2 size={16} /> Model profiles</button><div className="local-badge"><span /> Local server · private</div></div>
    </aside>
    <main className="workspace">
      <header className="topbar"><div><span className="eyebrow">ACTIVE CHRONICLE</span><h1>{selected?.title || "No chronicle selected"}</h1></div><div className="top-actions"><span className="status-pill"><span /> {selected ? "TABLE OPEN" : "WAITING"}</span><button className="icon-button" title="Save chronicle" onClick={saveChronicle}><Save size={17} /></button><button className="icon-button" title="Open rulesets" onClick={() => setNotice(`${rulesets.length} rulesets installed.`)}><BookOpen size={17} /></button></div></header>
      <div className="content-grid">
        <section className="play-panel"><div className="scene-strip"><div><span className="eyebrow">CURRENT SCENE</span><h2>{selected ? "The table is waiting for a choice" : "Choose a chronicle"}</h2></div><div className="scene-meta"><span><Dice5 size={15} /> server dice</span><span><MessageSquare size={15} /> {messages.length} messages</span></div></div><div className="chat-log">{selected && messages.length === 0 && <div className="empty-state"><Sparkles size={25} /><p>Your opening scene is waiting.</p><small>Send an action below to begin the chronicle.</small></div>}{messages.map((message) => <article className={`message ${message.speaker_kind}`} key={message.id}><div className="message-label">{message.speaker_kind === "player" ? "YOU" : message.speaker_kind.toUpperCase()}</div><p>{message.content}</p></article>)}</div><form className="turn-composer" onSubmit={sendTurn}><textarea value={draft} onChange={(event) => setDraft(event.target.value)} disabled={!selected || loading} placeholder={selected ? "What do you do?" : "Select a chronicle first"} /><button className="send-button" title="Send turn" disabled={!selected || loading || !draft.trim()}><Send size={18} /></button></form><div className="notice">{notice}</div></section>
        <aside className="inspector"><div className="inspector-heading"><span className="eyebrow">TABLE CARD</span><Settings2 size={16} /></div><div className="card-rule" /><dl><div><dt>RULESET</dt><dd>{selected?.ruleset_id || "freeform"}</dd></div><div><dt>SETTING</dt><dd>{selected?.setting_pack_id || "default"}</dd></div><div><dt>MODE</dt><dd>{selected?.mode || "group"}</dd></div><div><dt>RULESETS INSTALLED</dt><dd>{rulesets.length || "--"}</dd></div></dl><div className="inspector-block"><span className="eyebrow">QUICK TOOLS</span><button onClick={rollServerDice}><Dice5 size={15} /> Roll dice</button><button onClick={saveChronicle}><Save size={15} /> Named save</button><button onClick={() => openUtility("saves")}><Save size={15} /> Browse saves</button><button onClick={() => openUtility("sheets")}><BookOpen size={15} /> Character sheets</button><button onClick={prepareSession}><BookOpen size={15} /> Prepare session</button></div></aside>
      </div>
    </main>
      {showSetup && selected && <div className="setup-overlay"><section className="setup-dialog"><div className="setup-header"><div><span className="eyebrow">SESSION ZERO</span><h2>{selected.title}</h2></div><button className="icon-button" onClick={() => setShowSetup(false)} title="Close setup">×</button></div><div className="setup-progress"><span className="done">01 CHRONICLE BIBLE</span><span>02 PLAYERS</span><span>03 OPENING SCENE</span></div><label>PREMISE<textarea value={bible?.premise || ""} readOnly /></label><label>PLAYER PITCH<textarea value={bible?.pitch_for_players || ""} readOnly /></label><div className="setup-columns"><div><span className="eyebrow">THEMES</span><div className="theme-list">{(bible?.themes || []).map((theme) => <span key={theme}>{theme}</span>)}</div></div><div><span className="eyebrow">OPENING SITUATION</span><p className="setup-opening">{bible?.opening_situation}</p></div></div><div className="setup-footer"><span className="notice">Review is local and saved to the campaign event log.</span><button className="primary-action" onClick={async () => { if (!selected) return; await api(`/campaigns/${selected.id}/session-zero/complete`, { method: "POST" }); setShowSetup(false); setNotice("Session zero complete. The opening scene is ready."); }}>Open the table <Sparkles size={15} /></button></div></section></div>}
      {utility && <div className="setup-overlay"><section className="utility-dialog"><div className="setup-header"><div><span className="eyebrow">TABLE LIBRARY</span><h2>{utility === "packs" ? "Rulesets" : utility === "saves" ? "Named saves" : utility === "sheets" ? "Character sheets" : utility === "documents" ? "PDF library" : "Model profiles"}</h2></div><button className="icon-button" onClick={() => { setUtility(null); setActiveSheet(null); }} title="Close panel">×</button></div><div className="utility-list">{utilityItems.length === 0 && <p className="notice">Nothing saved here yet.</p>}{utilityItems.map((item, index) => <button className="utility-row" key={index} onClick={() => utility === "sheets" ? openSheet(item as Sheet) : undefined}><b>{(item as Ruleset | Sheet).name || (item as { title?: string; id?: string }).title || (item as { id?: string }).id || "Untitled"}</b><span>{(item as Ruleset).version || (item as Sheet).template_key || (item as { genres?: string[] }).genres?.join(", ") || "ready"}</span></button>)}</div>{activeSheet && <div className="sheet-editor"><span className="eyebrow">SHEET V{activeSheet.version || 1}</span>{(activeSheet.field_schema || []).map((field) => <label key={field.name}>{field.label || field.name}<input type={field.type === "number" ? "number" : "text"} value={String(activeSheet.fields?.[field.name] ?? "")} onChange={(event) => setActiveSheet({ ...activeSheet, fields: { ...activeSheet.fields, [field.name]: field.type === "number" ? Number(event.target.value) : event.target.value } })} /></label>)}<button className="primary-action" onClick={saveSheet}>Save sheet <Save size={15} /></button></div>}</section></div>}
  </div>;
}
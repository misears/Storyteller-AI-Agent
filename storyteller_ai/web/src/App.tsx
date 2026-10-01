import { FormEvent, useEffect, useState } from "react";
import { BookOpen, Dice5, Library, MessageSquare, Plus, Save, Send, Settings2, Sparkles } from "lucide-react";

type Campaign = { id: string; title: string; status: string; mode: string; ruleset_id: string; setting_pack_id: string };
type ChatMessage = { id: string; speaker_kind: string; content: string; seq: number };
type Ruleset = { id: string; name: string; version: string; mechanic?: string };

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

  async function refresh() {
    const [campaignData, rulesetData] = await Promise.all([
      api<Campaign[]>("/campaigns/"), api<Ruleset[]>("/rulesets")
    ]);
    setCampaigns(campaignData); setRulesets(rulesetData);
  }
  useEffect(() => { refresh().catch((error) => setNotice(error.message)); }, []);

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

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Sparkles size={17} /></div><div><strong>STORYTELLER</strong><span>chronicle desk</span></div></div>
      <div className="side-label">YOUR CHRONICLES</div>
      <div className="campaign-list">{campaigns.map((campaign) => <button className={`campaign-item ${selected?.id === campaign.id ? "active" : ""}`} key={campaign.id} onClick={() => openCampaign(campaign)}><span className="campaign-dot" /><span><b>{campaign.title || "Untitled"}</b><small>{campaign.status.replace("_", " ")} · {campaign.mode}</small></span></button>)}</div>
      <form className="new-campaign" onSubmit={createCampaign}><input value={newTitle} onChange={(event) => setNewTitle(event.target.value)} placeholder="Name a new chronicle" /><button title="Create chronicle" disabled={loading}><Plus size={17} /></button></form>
      <div className="sidebar-bottom"><button><Library size={16} /> Pack library</button><button><Settings2 size={16} /> Table settings</button><div className="local-badge"><span /> Local server · private</div></div>
    </aside>
    <main className="workspace">
      <header className="topbar"><div><span className="eyebrow">ACTIVE CHRONICLE</span><h1>{selected?.title || "No chronicle selected"}</h1></div><div className="top-actions"><span className="status-pill"><span /> {selected ? "TABLE OPEN" : "WAITING"}</span><button className="icon-button" title="Save chronicle"><Save size={17} /></button><button className="icon-button" title="Open rulesets"><BookOpen size={17} /></button></div></header>
      <div className="content-grid">
        <section className="play-panel"><div className="scene-strip"><div><span className="eyebrow">CURRENT SCENE</span><h2>{selected ? "The table is waiting for a choice" : "Choose a chronicle"}</h2></div><div className="scene-meta"><span><Dice5 size={15} /> server dice</span><span><MessageSquare size={15} /> {messages.length} messages</span></div></div><div className="chat-log">{selected && messages.length === 0 && <div className="empty-state"><Sparkles size={25} /><p>Your opening scene is waiting.</p><small>Send an action below to begin the chronicle.</small></div>}{messages.map((message) => <article className={`message ${message.speaker_kind}`} key={message.id}><div className="message-label">{message.speaker_kind === "player" ? "YOU" : message.speaker_kind.toUpperCase()}</div><p>{message.content}</p></article>)}</div><form className="turn-composer" onSubmit={sendTurn}><textarea value={draft} onChange={(event) => setDraft(event.target.value)} disabled={!selected || loading} placeholder={selected ? "What do you do?" : "Select a chronicle first"} /><button className="send-button" title="Send turn" disabled={!selected || loading || !draft.trim()}><Send size={18} /></button></form><div className="notice">{notice}</div></section>
        <aside className="inspector"><div className="inspector-heading"><span className="eyebrow">TABLE CARD</span><Settings2 size={16} /></div><div className="card-rule" /><dl><div><dt>RULESET</dt><dd>{selected?.ruleset_id || "freeform"}</dd></div><div><dt>SETTING</dt><dd>{selected?.setting_pack_id || "default"}</dd></div><div><dt>MODE</dt><dd>{selected?.mode || "group"}</dd></div><div><dt>RULESETS INSTALLED</dt><dd>{rulesets.length || "--"}</dd></div></dl><div className="inspector-block"><span className="eyebrow">QUICK TOOLS</span><button><Dice5 size={15} /> Roll dice</button><button><Save size={15} /> Named save</button><button><BookOpen size={15} /> Look up rules</button></div></aside>
      </div>
    </main>
  </div>;
}
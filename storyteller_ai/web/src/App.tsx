import { FormEvent, useEffect, useRef, useState } from "react";
import { BookOpen, Dice5, Download, Library, MessageSquare, Plus, Save, Send, Settings2, Sparkles, Upload, X } from "lucide-react";

type Campaign = { id: string; title: string; status: string; mode: string; ruleset_id: string; setting_pack_id: string; source_document_ids?: string[]; chronicle_document_id?: string | null; chronicle_page?: number };
type ChatMessage = { id: string; speaker_kind: string; content: string; seq: number };
type Ruleset = { id: string; name: string; version: string; mechanic?: string };
type Bible = { premise: string; pitch_for_players: string; themes: string[]; opening_situation: string };
type Advancement = { id: string; kind: "award" | "spend" | "change"; xp: number; fields: Record<string, string | number>; name?: string | null; reason: string; base_version: number; status: string; ai_review?: { recommendation: string; reason: string; citations: { document_id: string; page: number }[] } | null; decided_by?: string; decision_reason?: string };
type Sheet = { sheet_id: string; name: string; template_key: string; version?: number; fields?: Record<string, string | number>; field_schema?: { name: string; label?: string; type?: string }[]; campaign_id?: string | null; experience?: { earned: number; spent: number; available: number }; advancement_requests?: Advancement[] };
type SheetTemplate = { key: string; name: string };
type DocumentRole = "core_rules" | "supplement" | "flavor" | "chronicle" | "reference";
const documentRoles: { value: DocumentRole; label: string }[] = [{ value: "core_rules", label: "Core rules" }, { value: "supplement", label: "Rules supplement" }, { value: "flavor", label: "Setting / flavor" }, { value: "chronicle", label: "Runnable chronicle" }, { value: "reference", label: "Unclassified reference" }];
type SourceDocument = { document_id: string; title: string; size: number; genres: string[]; role: DocumentRole; page_count: number };
type SourcePage = { document_id: string; title: string; page: number; text: string };
type PackImport = { id: string; status: string; draft: Record<string, unknown>; errors: string[] };
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
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...init, headers });
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
  const [utility, setUtility] = useState<"packs" | "saves" | "sheets" | "documents" | "profiles" | "ai" | "sources" | null>(null);
  const [utilityItems, setUtilityItems] = useState<unknown[]>([]);
  const [utilityNotice, setUtilityNotice] = useState("");
  const [utilityBusy, setUtilityBusy] = useState(false);
  const [pdfFiles, setPdfFiles] = useState<File[]>([]);
  const [pdfGenres, setPdfGenres] = useState("");
  const [pdfRole, setPdfRole] = useState<DocumentRole>("reference");
  const [pdfPreview, setPdfPreview] = useState<SourcePage[]>([]);
  const [campaignDocumentIds, setCampaignDocumentIds] = useState<string[]>([]);
  const [campaignRuleset, setCampaignRuleset] = useState("freeform");
  const [scenarioDocument, setScenarioDocument] = useState("");
  const [scenarioPage, setScenarioPage] = useState(1);
  const pdfInputRef = useRef<HTMLInputElement | null>(null);
  const [sourceDocuments, setSourceDocuments] = useState<SourceDocument[]>([]);
  const [importDocumentIds, setImportDocumentIds] = useState<string[]>([]);
  const [importName, setImportName] = useState("");
  const [importMode, setImportMode] = useState<"new" | "extend">("new");
  const [importTarget, setImportTarget] = useState("");
  const [packImport, setPackImport] = useState<PackImport | null>(null);
  const [packDraft, setPackDraft] = useState("");
  const [rulesetDetail, setRulesetDetail] = useState<Record<string, unknown> | null>(null);
  const [sheetTemplates, setSheetTemplates] = useState<SheetTemplate[]>([]);
  const [newSheetName, setNewSheetName] = useState("");
  const [newSheetTemplate, setNewSheetTemplate] = useState("");
  const [activeSheet, setActiveSheet] = useState<Sheet | null>(null);
  const [sheetBaseline, setSheetBaseline] = useState<Sheet | null>(null);
  const [sheetCampaign, setSheetCampaign] = useState("");
  const [xpKind, setXpKind] = useState<Advancement["kind"]>("award");
  const [xpAmount, setXpAmount] = useState(1);
  const [xpReason, setXpReason] = useState("");
  const [reviewGuidance, setReviewGuidance] = useState("");
  const [humanReviewer, setHumanReviewer] = useState("");
  const [decisionReason, setDecisionReason] = useState("");
  const [humanConfirmed, setHumanConfirmed] = useState(false);
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
    setUtility(kind); setUtilityItems([]); setActiveSheet(null); setRulesetDetail(null);
    setUtilityNotice(""); setUtilityBusy(true);
    setPdfPreview([]); setHumanConfirmed(false);
    try {
      const path = kind === "packs" ? "/rulesets" : kind === "saves" ? `/campaigns/${selected?.id}/saves` : kind === "sheets" ? "/character-sheets/" : kind === "documents" ? "/documents/list" : "/settings/llm/profiles";
      const result = await api<unknown>(path);
      const wrapper = result as { saves?: unknown[]; sheets?: unknown[]; documents?: unknown[]; profiles?: Record<string, unknown> };
      const profiles = wrapper.profiles ? Object.entries(wrapper.profiles).map(([role, profile]) => ({ name: role, ...profile as object })) : [];
      setUtilityItems(Array.isArray(result) ? result : (wrapper.saves || wrapper.sheets || wrapper.documents || profiles));
      if (kind === "sheets") {
        const result = await api<{ templates: SheetTemplate[] }>("/character-sheets/templates");
        setSheetTemplates(result.templates);
        setNewSheetTemplate((current) => current || result.templates[0]?.key || "");
      }
      if (kind === "packs") {
        const result = await api<{ documents: SourceDocument[] }>("/documents/list");
        setSourceDocuments(result.documents);
      }
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not load panel"); }
    finally { setUtilityBusy(false); }
  }

  async function uploadDocuments(event: FormEvent) {
    event.preventDefault(); if (!pdfFiles.length) return;
    setUtilityBusy(true); setUtilityNotice("Uploading PDFs...");
    try {
      const body = new FormData();
      pdfFiles.forEach((file) => body.append("files", file));
      body.append("genres", pdfGenres);
      body.append("role", pdfRole);
      const uploaded = await api<{ documents: SourceDocument[] }>("/documents/upload", { method: "POST", body });
      const result = await api<{ documents: SourceDocument[] }>("/documents/list");
      setUtilityItems(result.documents); setPdfFiles([]);
      if (pdfInputRef.current) pdfInputRef.current.value = "";
      setUtilityNotice(`${uploaded.documents.length} PDF(s) uploaded.`);
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "PDF upload failed"); }
    finally { setUtilityBusy(false); }
  }

  async function viewRuleset(ruleset: Ruleset) {
    try {
      setRulesetDetail(await api<Record<string, unknown>>(`/rulesets/${encodeURIComponent(ruleset.id)}?version=${encodeURIComponent(ruleset.version)}`));
      setUtilityNotice("");
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not open ruleset"); }
  }

  async function startPackImport(event: FormEvent) {
    event.preventDefault(); if (!importDocumentIds.length || !importName.trim()) return;
    setUtilityBusy(true); setUtilityNotice("");
    try {
      const job = await api<PackImport>("/rulesets/imports", { method: "POST", body: JSON.stringify({ document_ids: importDocumentIds, mode: importMode, target_pack_id: importMode === "extend" ? importTarget : null }) });
      const draft = await api<PackImport>(`/rulesets/imports/${job.id}/answers`, { method: "POST", body: JSON.stringify({ fields: { manifest: { name: importName.trim() } } }) });
      setPackImport(draft); setPackDraft(JSON.stringify(draft.draft, null, 2));
      setUtilityNotice("Draft ready for review. Not installed.");
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not start ruleset import"); }
    finally { setUtilityBusy(false); }
  }

  async function validatePackDraft() {
    if (!packImport) return;
    setUtilityBusy(true); setUtilityNotice("");
    try {
      const fields: unknown = JSON.parse(packDraft);
      if (!fields || typeof fields !== "object" || Array.isArray(fields)) throw new Error("Ruleset draft must be a JSON object.");
      await api(`/rulesets/imports/${packImport.id}/answers`, { method: "POST", body: JSON.stringify({ fields }) });
      const job = await api<PackImport>(`/rulesets/imports/${packImport.id}/validate`, { method: "POST" });
      setPackImport(job); setUtilityNotice(job.errors.length ? job.errors.join("\n") : "Draft validated. Ready to install.");
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Draft validation failed"); }
    finally { setUtilityBusy(false); }
  }

  async function commitPackImport() {
    if (!packImport || packImport.status !== "validated") return;
    setUtilityBusy(true);
    try {
      await api(`/rulesets/imports/${packImport.id}/commit`, { method: "POST" });
      const result = await api<Ruleset[]>("/rulesets");
      setRulesets(result); setUtilityItems(result); setPackImport(null); setImportName(""); setImportDocumentIds([]);
      setUtilityNotice("Ruleset installed.");
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not install ruleset"); }
    finally { setUtilityBusy(false); }
  }

  async function createSheet(event: FormEvent) {
    event.preventDefault(); if (!newSheetName.trim() || !newSheetTemplate) return;
    setUtilityBusy(true); setUtilityNotice("");
    try {
      const result = await api<{ sheet: Sheet }>("/character-sheets/", { method: "POST", body: JSON.stringify({ name: newSheetName.trim(), template_key: newSheetTemplate }) });
      setActiveSheet(result.sheet); setSheetBaseline(result.sheet); setSheetCampaign(selected?.id || ""); setNewSheetName("");
      const list = await api<{ sheets: Sheet[] }>("/character-sheets/");
      setUtilityItems(list.sheets); setUtilityNotice("Character sheet created.");
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not create character sheet"); }
    finally { setUtilityBusy(false); }
  }

  async function openAISetup() {
    setUtility("ai"); setUtilityNotice(""); setAiSetup(null); setUtilityBusy(true);
    try {
      const status = await api<AISetupState>("/settings/ai");
      setAiSetup(status);
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not load AI setup"); }
    finally { setUtilityBusy(false); }
  }

  async function refreshAISetup() {
    const status = await api<AISetupState>("/settings/ai");
    setAiSetup(status);
  }

  async function saveAISetup() {
    if (!aiSetup) return;
    setUtilityBusy(true); setUtilityNotice("Saving AI provider settings...");
    try {
      const status = await api<AISetupState>("/settings/ai", {
        method: "PUT",
        body: JSON.stringify({ provider: aiSetup.provider, model: aiSetup.model, ollama_mode: aiSetup.ollama_mode }),
      });
      setAiSetup(status); setUtilityNotice("AI provider settings saved.");
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not save AI settings"); }
    finally { setUtilityBusy(false); }
  }

  async function saveAIKey() {
    if (!aiSetup || !aiKey.trim()) return;
    const provider = aiSetup.provider;
    if (provider === "ollama") return;
    const secret = aiKey;
    setAiKey("");
    try {
      await api(`/settings/ai/credentials/${provider}`, { method: "PUT", body: JSON.stringify({ api_key: secret }) });
      await refreshAISetup(); setUtilityNotice(`${provider} key saved securely.`);
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not save provider key"); }
  }

  async function removeAIKey(provider: "openai" | "anthropic") {
    try {
      await api(`/settings/ai/credentials/${provider}`, { method: "DELETE" });
      await refreshAISetup(); setUtilityNotice(`${provider} key removed.`);
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not remove provider key"); }
  }

  async function testAIProvider() {
    setUtilityBusy(true); setUtilityNotice("Testing provider connection...");
    try {
      await api("/settings/ai/test", { method: "POST" });
      setUtilityNotice("Provider connection test succeeded.");
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Provider test failed"); }
    finally { setUtilityBusy(false); }
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
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not start model download"); }
  }

  async function cancelModelPull() {
    if (!pullJob) return;
    try {
      await api(`/settings/ai/models/pull/${pullJob.id}`, { method: "DELETE" });
      setPullJob({ ...pullJob, status: "cancelled", progress: "Download cancelled" });
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not cancel model download"); }
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
    try {
      const result = await api<{ sheet: Sheet }>(`/character-sheets/${sheet.sheet_id}`);
      setActiveSheet(result.sheet); setSheetBaseline(result.sheet); setSheetCampaign(result.sheet.campaign_id || selected?.id || ""); setHumanConfirmed(false); setUtilityNotice("");
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not open sheet"); }
  }

  async function saveSheet() {
    if (!activeSheet) return;
    setUtilityBusy(true);
    try {
      const result = await api<{ sheet: Sheet }>(`/character-sheets/${activeSheet.sheet_id}`, { method: "PUT", body: JSON.stringify({ name: activeSheet.name, fields: activeSheet.fields, expected_version: activeSheet.version }) });
      setActiveSheet(result.sheet);
      setSheetBaseline(result.sheet);
      setUtilityItems((items) => items.map((item) => (item as Sheet).sheet_id === result.sheet.sheet_id ? result.sheet : item));
      setUtilityNotice("Character sheet saved.");
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not save sheet"); }
    finally { setUtilityBusy(false); }
  }

  async function changeDocumentRole(document: SourceDocument, role: DocumentRole) {
    setUtilityBusy(true);
    try {
      await api(`/documents/${encodeURIComponent(document.document_id)}/role`, { method: "PUT", body: JSON.stringify({ role }) });
      setUtilityItems((items) => items.map((item) => (item as SourceDocument).document_id === document.document_id ? { ...document, role } : item));
      setUtilityNotice("PDF role saved.");
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not save PDF role"); }
    finally { setUtilityBusy(false); }
  }

  async function previewDocument(documentId: string, startPage = 1) {
    try {
      const result = await api<{ pages: SourcePage[] }>(`/documents/${encodeURIComponent(documentId)}/pages?start_page=${startPage}`);
      setPdfPreview(result.pages);
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not open PDF pages"); }
  }

  async function openSources() {
    if (!selected) return;
    setUtility("sources"); setUtilityItems([]); setActiveSheet(null); setUtilityNotice(""); setUtilityBusy(true); setPdfPreview([]);
    setCampaignDocumentIds(selected.source_document_ids || []); setCampaignRuleset(selected.ruleset_id);
    setScenarioDocument(selected.chronicle_document_id || ""); setScenarioPage(selected.chronicle_page || 1);
    try { setSourceDocuments((await api<{ documents: SourceDocument[] }>("/documents/list")).documents); }
    catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not load chronicle sources"); }
    finally { setUtilityBusy(false); }
  }

  async function saveSources(event: FormEvent) {
    event.preventDefault(); if (!selected) return;
    setUtilityBusy(true);
    try {
      const updated = await api<Campaign>(`/campaigns/${selected.id}/sources`, { method: "PUT", body: JSON.stringify({ document_ids: campaignDocumentIds, ruleset_id: campaignRuleset, chronicle_document_id: scenarioDocument || null, chronicle_page: scenarioPage }) });
      setSelected(updated); await refresh(); setUtilityNotice("Chronicle sources saved.");
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not save chronicle sources"); }
    finally { setUtilityBusy(false); }
  }

  async function reloadSheet(sheetId: string) {
    const result = await api<{ sheet: Sheet }>(`/character-sheets/${sheetId}`);
    setActiveSheet(result.sheet); setSheetBaseline(result.sheet);
    setUtilityItems((items) => items.map((item) => (item as Sheet).sheet_id === sheetId ? result.sheet : item));
  }

  async function linkSheetCampaign() {
    if (!activeSheet || !sheetCampaign) return;
    setUtilityBusy(true);
    try {
      if (sheetBaseline && (activeSheet.name !== sheetBaseline.name || JSON.stringify(activeSheet.fields) !== JSON.stringify(sheetBaseline.fields))) throw new Error("Save the initial character sheet before linking it to a chronicle.");
      await api(`/character-sheets/${activeSheet.sheet_id}/campaign`, { method: "PUT", body: JSON.stringify({ campaign_id: sheetCampaign, expected_version: activeSheet.version }) });
      await reloadSheet(activeSheet.sheet_id); setUtilityNotice("Character linked to chronicle.");
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not link character"); }
    finally { setUtilityBusy(false); }
  }

  async function proposeAdvancement(event: FormEvent) {
    event.preventDefault(); if (!activeSheet || !sheetBaseline) return;
    setUtilityBusy(true); setUtilityNotice("");
    try {
      const fields = xpKind === "award" ? {} : Object.fromEntries(Object.entries(activeSheet.fields || {}).filter(([name, value]) => value !== sheetBaseline.fields?.[name]));
      await api(`/character-sheets/${activeSheet.sheet_id}/advancement`, { method: "POST", body: JSON.stringify({ kind: xpKind, xp: xpKind === "change" ? 0 : xpAmount, fields, name: xpKind !== "award" && activeSheet.name !== sheetBaseline.name ? activeSheet.name : null, reason: xpReason, expected_version: sheetBaseline.version }) });
      await reloadSheet(activeSheet.sheet_id); setXpReason(""); setUtilityNotice("Request submitted. XP and sheet are unchanged pending review and approval.");
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not submit request"); }
    finally { setUtilityBusy(false); }
  }

  async function reviewAdvancement(request: Advancement) {
    if (!activeSheet) return;
    setUtilityBusy(true); setUtilityNotice("AI Storyteller is reviewing the request...");
    try {
      await api(`/character-sheets/${activeSheet.sheet_id}/advancement/${request.id}/review`, { method: "POST", body: JSON.stringify({ storyteller_guidance: reviewGuidance }) });
      await reloadSheet(activeSheet.sheet_id); setUtilityNotice("AI review complete. Awaiting human Storyteller decision.");
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "AI review failed; no changes applied"); }
    finally { setUtilityBusy(false); }
  }

  async function decideAdvancement(request: Advancement, approve: boolean) {
    if (!activeSheet || !humanConfirmed) return;
    setUtilityBusy(true);
    try {
      await api(`/character-sheets/${activeSheet.sheet_id}/advancement/${request.id}/decision`, { method: "POST", body: JSON.stringify({ approve, reviewer: humanReviewer, reason: decisionReason, human_confirmation: humanConfirmed }) });
      await reloadSheet(activeSheet.sheet_id); setHumanConfirmed(false); setDecisionReason("");
      setUtilityNotice(approve ? "Approved. XP and character sheet updated." : "Request rejected. No XP or sheet changes applied.");
    } catch (error) { setUtilityNotice(error instanceof Error ? error.message : "Could not record decision"); }
    finally { setUtilityBusy(false); }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Sparkles size={17} /></div><div><strong>STORYTELLER</strong><span>chronicle desk</span></div></div>
      <div className="side-label">YOUR CHRONICLES</div>
      <div className="campaign-list">{campaigns.map((campaign) => <button className={`campaign-item ${selected?.id === campaign.id ? "active" : ""}`} key={campaign.id} onClick={() => openCampaign(campaign)}><span className="campaign-dot" /><span><b>{campaign.title || "Untitled"}</b><small>{campaign.status.replace("_", " ")} · {campaign.mode}</small></span></button>)}</div>
      <form className="new-campaign" onSubmit={createCampaign}><input value={newTitle} onChange={(event) => setNewTitle(event.target.value)} placeholder="Name a new chronicle" /><button title="Create chronicle" disabled={loading}><Plus size={17} /></button></form>
      <div className="sidebar-bottom"><button onClick={() => openUtility("packs")}><Library size={16} /> Pack library</button><button onClick={() => openUtility("documents")}><BookOpen size={16} /> PDF library</button><button onClick={openSources} disabled={!selected}><BookOpen size={16} /> Chronicle sources</button><button onClick={() => openUtility("sheets")}><BookOpen size={16} /> Character sheets</button><button onClick={() => openUtility("profiles")}><Settings2 size={16} /> Model profiles</button><button onClick={openAISetup}><Settings2 size={16} /> AI provider setup</button><div className="local-badge"><span /> Local server · private</div></div>
    </aside>
    <main className="workspace">
      <header className="topbar"><div><span className="eyebrow">ACTIVE CHRONICLE</span><h1>{selected?.title || "No chronicle selected"}</h1></div><div className="top-actions"><span className="status-pill"><span /> {selected ? "TABLE OPEN" : "WAITING"}</span><button className="icon-button" title="AI provider setup" onClick={openAISetup}><Settings2 size={17} /></button><button className="icon-button" title="Save chronicle" onClick={saveChronicle} disabled={!selected}><Save size={17} /></button><button className="icon-button" title="Open rulesets" onClick={() => openUtility("packs")}><BookOpen size={17} /></button></div></header>
      <div className="content-grid">
        <section className="play-panel"><div className="scene-strip"><div><span className="eyebrow">CURRENT SCENE</span><h2>{selected ? "The table is waiting for a choice" : "Choose a chronicle"}</h2></div><div className="scene-meta"><span><Dice5 size={15} /> server dice</span><span><MessageSquare size={15} /> {messages.length} messages</span></div></div><div className="chat-log">{selected && messages.length === 0 && <div className="empty-state"><Sparkles size={25} /><p>Your opening scene is waiting.</p><small>Send an action below to begin the chronicle.</small></div>}{messages.map((message) => <article className={`message ${message.speaker_kind}`} key={message.id}><div className="message-label">{message.speaker_kind === "player" ? "YOU" : message.speaker_kind.toUpperCase()}</div><p>{message.content}</p></article>)}</div><form className="turn-composer" onSubmit={sendTurn}><textarea value={draft} onChange={(event) => setDraft(event.target.value)} disabled={!selected || loading} placeholder={selected ? "What do you do?" : "Select a chronicle first"} />{loading ? <div className="turn-progress"><span>Generating · {turnElapsed}s</span><button type="button" className="cancel-turn" onClick={cancelTurn} title="Cancel generation"><X size={16} /> Cancel</button></div> : <button className="send-button" title="Send turn" disabled={!selected || !draft.trim()}><Send size={18} /></button>}</form><div className="notice">{notice}</div></section>
        <aside className="inspector"><div className="inspector-heading"><span className="eyebrow">TABLE CARD</span><Settings2 size={16} /></div><div className="card-rule" /><dl><div><dt>RULESET</dt><dd>{selected?.ruleset_id || "freeform"}</dd></div><div><dt>SETTING</dt><dd>{selected?.setting_pack_id || "default"}</dd></div><div><dt>MODE</dt><dd>{selected?.mode || "group"}</dd></div><div><dt>RULESETS INSTALLED</dt><dd>{rulesets.length || "--"}</dd></div></dl><div className="inspector-block"><span className="eyebrow">QUICK TOOLS</span><button onClick={rollServerDice} disabled={!selected}><Dice5 size={15} /> Roll dice</button><button onClick={saveChronicle} disabled={!selected}><Save size={15} /> Named save</button><button onClick={() => openUtility("saves")} disabled={!selected}><Save size={15} /> Browse saves</button><button onClick={() => openUtility("sheets")}><BookOpen size={15} /> Character sheets</button><button onClick={prepareSession} disabled={!selected}><BookOpen size={15} /> Prepare session</button></div></aside>
      </div>
    </main>
      {showSetup && selected && <div className="setup-overlay"><section className="setup-dialog"><div className="setup-header"><div><span className="eyebrow">SESSION ZERO</span><h2>{selected.title}</h2></div><button className="icon-button" onClick={() => setShowSetup(false)} title="Close setup">×</button></div><div className="setup-progress"><span className="done">01 CHRONICLE BIBLE</span><span>02 PLAYERS</span><span>03 OPENING SCENE</span></div><label>PREMISE<textarea value={bible?.premise || ""} readOnly /></label><label>PLAYER PITCH<textarea value={bible?.pitch_for_players || ""} readOnly /></label><div className="setup-columns"><div><span className="eyebrow">THEMES</span><div className="theme-list">{(bible?.themes || []).map((theme) => <span key={theme}>{theme}</span>)}</div></div><div><span className="eyebrow">OPENING SITUATION</span><p className="setup-opening">{bible?.opening_situation}</p></div></div><div className="setup-footer"><span className="notice">Review is local and saved to the campaign event log.</span><button className="primary-action" onClick={async () => { if (!selected) return; await api(`/campaigns/${selected.id}/session-zero/complete`, { method: "POST" }); setShowSetup(false); setNotice("Session zero complete. The opening scene is ready."); }}>Open the table <Sparkles size={15} /></button></div></section></div>}
      {utility && <div className="setup-overlay"><section role="dialog" aria-modal="true" aria-labelledby="utility-heading" className={`utility-dialog ${utility === "ai" ? "ai-dialog" : ""}`}><div className="setup-header"><div><span className="eyebrow">{utility === "ai" ? "AI PROVIDER" : "TABLE LIBRARY"}</span><h2 id="utility-heading">{utility === "packs" ? "Rulesets" : utility === "saves" ? "Named saves" : utility === "sheets" ? "Character sheets" : utility === "documents" ? "PDF library" : utility === "profiles" ? "Model profiles" : utility === "sources" ? "Chronicle sources" : "AI setup"}</h2></div><button className="icon-button" onClick={() => { setUtility(null); setActiveSheet(null); setAiKey(""); }} title="Close panel"><X size={17} /></button></div><p className="utility-notice" role="status">{utilityNotice || (utilityBusy ? "Loading..." : "")}</p>{utility === "ai" ? <div className="ai-settings">
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
          <div className="ai-actions"><button className="primary-action" disabled={utilityBusy} onClick={saveAISetup}>Save provider settings</button><button className="secondary-action" disabled={utilityBusy} onClick={testAIProvider}>Test provider</button></div>
        </>}
      </div> : <>
        {utility === "documents" && <form className="library-form" onSubmit={uploadDocuments}>
          <label>PDF files<input ref={pdfInputRef} type="file" accept=".pdf,application/pdf" multiple required onChange={(event) => setPdfFiles(Array.from(event.target.files || []))} /></label>
          <label>Genres<input value={pdfGenres} onChange={(event) => setPdfGenres(event.target.value)} placeholder="horror, fantasy" /></label>
          <label>Upload PDF role<select value={pdfRole} onChange={(event) => setPdfRole(event.target.value as DocumentRole)}>{documentRoles.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}</select></label>
          <button className="primary-action" disabled={utilityBusy || !pdfFiles.length}><Upload size={15} /> Upload PDFs</button>
        </form>}
        {utility === "sources" && <form className="library-form" onSubmit={saveSources}>
          <label>Chronicle ruleset<select value={campaignRuleset} onChange={(event) => setCampaignRuleset(event.target.value)}>{rulesets.map((ruleset) => <option key={ruleset.id} value={ruleset.id}>{ruleset.name}</option>)}</select></label>
          <fieldset className="source-documents"><legend>Chronicle reference PDFs</legend>{sourceDocuments.filter((document) => document.role !== "chronicle").map((document) => <label key={document.document_id}><input type="checkbox" checked={campaignDocumentIds.includes(document.document_id)} onChange={(event) => setCampaignDocumentIds((current) => event.target.checked ? [...current, document.document_id] : current.filter((id) => id !== document.document_id))} /><span>{document.title} - {documentRoles.find((role) => role.value === document.role)?.label}</span></label>)}</fieldset>
          <label>Published chronicle<select value={scenarioDocument} onChange={(event) => { setScenarioDocument(event.target.value); setScenarioPage(1); setPdfPreview([]); }}><option value="">Original / freeform chronicle</option>{sourceDocuments.filter((document) => document.role === "chronicle").map((document) => <option key={document.document_id} value={document.document_id}>{document.title}</option>)}</select></label>
          {scenarioDocument && <><label>Current book page<input type="number" min={1} max={sourceDocuments.find((document) => document.document_id === scenarioDocument)?.page_count} value={scenarioPage} onChange={(event) => setScenarioPage(Number(event.target.value))} required /></label><button type="button" className="secondary-action" onClick={() => previewDocument(scenarioDocument, scenarioPage)}><BookOpen size={15} /> Preview current pages</button></>}
          <button className="primary-action" disabled={utilityBusy}><Save size={15} /> Save chronicle sources</button>
        </form>}
        {utility === "sheets" && <form className="library-form" onSubmit={createSheet}>
          <label>Character name<input value={newSheetName} required onChange={(event) => setNewSheetName(event.target.value)} /></label>
          <label>Character template<select value={newSheetTemplate} required onChange={(event) => setNewSheetTemplate(event.target.value)}>{sheetTemplates.map((template) => <option key={template.key} value={template.key}>{template.name}</option>)}</select></label>
          <button className="primary-action" disabled={utilityBusy || !newSheetName.trim() || !newSheetTemplate}><Plus size={15} /> Create character sheet</button>
        </form>}
        {utility !== "sources" && <div className="utility-list">{!utilityBusy && utilityItems.length === 0 && <p className="notice">Nothing saved here yet.</p>}{utilityItems.map((item, index) => {
          const itemName = (item as Ruleset | Sheet).name || (item as { title?: string; id?: string }).title || (item as { id?: string }).id || "Untitled";
          const itemDetail = (item as Ruleset).version || (item as Sheet).template_key || (item as { genres?: string[] }).genres?.join(", ") || "ready";
          return utility === "sheets" ? <button className="utility-row" key={index} onClick={() => openSheet(item as Sheet)}><b>{itemName}</b><span>{itemDetail}</span></button>
            : utility === "packs" ? <button className="utility-row" key={index} onClick={() => viewRuleset(item as Ruleset)}><b>{itemName}</b><span>{itemDetail}</span></button>
            : utility === "saves" ? <button className="utility-row" key={index} onClick={() => loadSave(String((item as { id?: string }).id || ""))}><b>{itemName}</b><span>Load timeline · seq {(item as { event_seq?: number }).event_seq ?? "--"}</span></button>
            : utility === "documents" ? <div className="document-row" key={(item as SourceDocument).document_id}><b>{itemName}</b><label>PDF role<select aria-label={`Role for ${itemName}`} value={(item as SourceDocument).role || "reference"} disabled={utilityBusy} onChange={(event) => changeDocumentRole(item as SourceDocument, event.target.value as DocumentRole)}>{documentRoles.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}</select></label><button className="secondary-action" onClick={() => previewDocument((item as SourceDocument).document_id)}><BookOpen size={15} /> Preview pages</button></div>
            : <div className="utility-row" key={index}><b>{itemName}</b><span>{itemDetail}</span></div>;
          })}</div>}
          {pdfPreview.length > 0 && <div className="library-section pdf-preview">{pdfPreview.map((page) => <article key={`${page.document_id}-${page.page}`}><h3>{page.title} - page {page.page}</h3><pre>{page.text}</pre></article>)}</div>}
        {utility === "packs" && <>
          {rulesetDetail && <div className="library-section"><h3>{String(rulesetDetail.name)}</h3><pre className="ruleset-detail">{JSON.stringify(rulesetDetail, null, 2)}</pre></div>}
          <form className="library-form library-section" onSubmit={startPackImport}>
            <h3>Import ruleset from PDFs</h3>
            <label>Import type<select value={importMode} onChange={(event) => { setImportMode(event.target.value as "new" | "extend"); setImportDocumentIds([]); }}><option value="new">New base ruleset</option><option value="extend">Extend base ruleset with supplement</option></select></label>
            {importMode === "extend" && <label>Base ruleset<select required value={importTarget} onChange={(event) => setImportTarget(event.target.value)}><option value="">Choose base ruleset</option>{rulesets.map((ruleset) => <option key={ruleset.id} value={ruleset.id}>{ruleset.name}</option>)}</select></label>}
            <label>Ruleset name<input required value={importName} onChange={(event) => setImportName(event.target.value)} /></label>
            <fieldset className="source-documents"><legend>Source PDFs</legend>{sourceDocuments.filter((document) => document.role === "core_rules" || document.role === "supplement").map((document) => <label key={document.document_id}><input type="checkbox" checked={importDocumentIds.includes(document.document_id)} onChange={(event) => setImportDocumentIds((current) => event.target.checked ? [...current, document.document_id] : current.filter((id) => id !== document.document_id))} /><span>{document.title} - {document.role === "supplement" ? "supplement" : "core rules"}</span></label>)}<button type="button" className="secondary-action" onClick={() => openUtility("documents")}><Upload size={15} /> Manage PDF roles</button></fieldset>
            <button className="primary-action" disabled={utilityBusy || !importName.trim() || !importDocumentIds.length || (importMode === "extend" && !importTarget)}><Plus size={15} /> Create ruleset draft</button>
          </form>
          {packImport && <div className="library-form library-section">
            <h3>Ruleset draft</h3><span className="eyebrow">{packImport.status}</span>
            <label>Ruleset draft (JSON)<textarea className="pack-draft" spellCheck={false} value={packDraft} onChange={(event) => { setPackDraft(event.target.value); setPackImport({ ...packImport, status: "draft" }); }} /></label>
            <div className="ai-actions"><button className="secondary-action" disabled={utilityBusy} onClick={validatePackDraft}><Save size={15} /> Save and validate draft</button><button className="primary-action" disabled={utilityBusy || packImport.status !== "validated"} onClick={commitPackImport}><Download size={15} /> Install ruleset</button></div>
          </div>}
        </>}
        {activeSheet && <div className="sheet-editor">
          <span className="eyebrow">SHEET V{activeSheet.version || 1}</span>
          <label>Sheet name<input value={activeSheet.name} onChange={(event) => setActiveSheet({ ...activeSheet, name: event.target.value })} /></label>
          {(activeSheet.field_schema || []).map((field) => <label key={field.name}>{field.label || field.name}{field.type === "textarea" ? <textarea value={String(activeSheet.fields?.[field.name] ?? "")} onChange={(event) => setActiveSheet({ ...activeSheet, fields: { ...activeSheet.fields, [field.name]: event.target.value } })} /> : <input type={field.type === "number" ? "number" : "text"} value={String(activeSheet.fields?.[field.name] ?? "")} onChange={(event) => setActiveSheet({ ...activeSheet, fields: { ...activeSheet.fields, [field.name]: field.type === "number" ? Number(event.target.value) : event.target.value } })} />}</label>)}
          {!activeSheet.campaign_id ? <>
            <button className="primary-action" disabled={utilityBusy} onClick={saveSheet}><Save size={15} /> Save sheet</button>
            <label>Character chronicle<select value={sheetCampaign} onChange={(event) => setSheetCampaign(event.target.value)}><option value="">Choose chronicle</option>{campaigns.map((campaign) => <option key={campaign.id} value={campaign.id}>{campaign.title || "Untitled chronicle"}</option>)}</select></label>
            <button className="secondary-action" disabled={utilityBusy || !sheetCampaign} onClick={linkSheetCampaign}><BookOpen size={15} /> Link character to chronicle</button>
          </> : <>
            <div className="xp-balance"><span>XP earned <b>{activeSheet.experience?.earned || 0}</b></span><span>XP spent <b>{activeSheet.experience?.spent || 0}</b></span><span>XP available <b>{activeSheet.experience?.available || 0}</b></span></div>
            <form className="library-form" onSubmit={proposeAdvancement}>
              <label>XP request type<select value={xpKind} onChange={(event) => setXpKind(event.target.value as Advancement["kind"])}><option value="award">Earn XP / session award</option><option value="spend">Spend XP on edited stats</option><option value="change">Sheet correction (no XP)</option></select></label>
              {xpKind !== "change" && <label>{xpKind === "award" ? "XP award" : "XP cost"}<input type="number" min={1} step={1} value={xpAmount} required onChange={(event) => setXpAmount(Number(event.target.value))} /></label>}
              <label>Advancement reason<textarea value={xpReason} required onChange={(event) => setXpReason(event.target.value)} /></label>
              <button className="primary-action" disabled={utilityBusy || !xpReason.trim()}><Send size={15} /> Submit advancement request</button>
            </form>
            <div className="library-form library-section">
              <h3>Storyteller review</h3>
              <label>Storyteller ruling / evidence<textarea value={reviewGuidance} onChange={(event) => setReviewGuidance(event.target.value)} /></label>
              <label>Human Storyteller name<input value={humanReviewer} onChange={(event) => setHumanReviewer(event.target.value)} /></label>
              <label>Decision reason<textarea value={decisionReason} onChange={(event) => setDecisionReason(event.target.value)} /></label>
              <label className="human-confirmation"><input type="checkbox" checked={humanConfirmed} onChange={(event) => setHumanConfirmed(event.target.checked)} /><span>I am the human Storyteller and confirm this decision</span></label>
            </div>
            <div className="advancement-list">{(activeSheet.advancement_requests || []).map((request) => <article className="advancement-request" key={request.id}>
              <h3>{request.kind === "award" ? "XP award" : request.kind === "spend" ? "XP advancement" : "Sheet correction"} - {request.xp} XP</h3><span className="eyebrow">{request.status}</span><p>{request.reason}</p>
              {Object.keys(request.fields).length > 0 && <pre>{JSON.stringify(request.fields, null, 2)}</pre>}
              {request.ai_review && <div className="ai-review"><b>AI review: {request.ai_review.recommendation.replaceAll("_", " ")}</b><p>{request.ai_review.reason}</p>{request.ai_review.citations.map((citation) => <small key={`${citation.document_id}-${citation.page}`}>{citation.document_id}, page {citation.page}</small>)}</div>}
              {request.decided_by && <p>{request.decided_by}: {request.decision_reason}</p>}
              {!['approved', 'rejected'].includes(request.status) && <div className="ai-actions">
                <button className="secondary-action" disabled={utilityBusy || request.base_version !== activeSheet.version} onClick={() => reviewAdvancement(request)}><Sparkles size={15} /> Request AI review</button>
                <button className="primary-action" disabled={utilityBusy || !humanConfirmed || !humanReviewer.trim() || !decisionReason.trim() || request.ai_review?.recommendation !== "approve" || request.base_version !== activeSheet.version} onClick={() => decideAdvancement(request, true)}><Save size={15} /> Approve advancement</button>
                <button className="secondary-action" disabled={utilityBusy || !humanConfirmed || !humanReviewer.trim() || !decisionReason.trim()} onClick={() => decideAdvancement(request, false)}><X size={15} /> Reject request</button>
              </div>}
              {!['approved', 'rejected'].includes(request.status) && request.base_version !== activeSheet.version && <p className="utility-notice">Outdated sheet version. Submit a new request.</p>}
            </article>)}</div>
          </>}
        </div>}
      </>}</section></div>}
  </div>;
}
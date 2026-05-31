import { useEffect, useRef, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const tabs = ["Chat Demo", "Email Ingest", "Usage", "Add Tenant", "Label Mapping"];

type EmailFormState = {
  message_id: string;
  from_email: string;
  to_email: string;
  subject: string;
  body: string;
};

type TenantFormState = {
  tenant_id: string;
  display_name: string;
  jira_project_key: string;
  jira_issue_type: string;
};

type LabelMappingFormState = {
  label_map: string;
};

type EmailIngestResponse = {
  status: string;
  message_id: string;
  tenant_id: string | null;
  intent: string;
  confidence: number;
  internal_tags: string[];
  handoff_summary?: Record<string, unknown> | null;
  jira_payload_preview?: Record<string, unknown> | null;
};

type JsonValue = Record<string, unknown> | null | undefined;

type ChatMessage = {
  role: "user" | "assistant";
  message: string;
};

type ChatResponse = {
  session_id: string;
  intent: string;
  confidence: number;
  reply: string;
  handoff: boolean;
  handoff_summary?: Record<string, unknown> | null;
  jira_payload_preview?: Record<string, unknown> | null;
};

type UsageSummaryResponse = {
  tenant_id: string | null;
  event_type_filter: string | null;
  total: number;
  by_event_type: Record<string, number>;
  by_intent?: Record<string, number>;
};

type BackendStatus = "checking" | "connected" | "offline";

type HealthResponse = {
  status?: string;
};

type Tenant = {
  tenant_id: string;
  display_name: string;
};

type TenantCreateResponse = {
  tenant_id: string;
  display_name: string;
  jira_project_key: string;
  jira_issue_type: string;
};

type TenantsResponse = {
  tenants: Tenant[];
};

type TenantLabelConfigResponse = {
  tenant_id: string;
  default_labels: string[];
  label_map: Record<string, string[]>;
};

const labelMapToText = (labelMap: Record<string, string[]>) =>
  JSON.stringify(labelMap ?? {}, null, 2);

const parseLabelMapJson = (value: string) => {
  const parsed = JSON.parse(value || "{}");

  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("Label map must be a JSON object");
  }

  for (const labels of Object.values(parsed)) {
    if (!Array.isArray(labels) || labels.some((label) => typeof label !== "string")) {
      throw new Error("Each label map value must be an array of strings");
    }
  }

  return parsed as Record<string, string[]>;
};

function fallbackCopyText(text: string) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  textarea.style.pointerEvents = "none";

  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();

  const copied = document.execCommand("copy");
  document.body.removeChild(textarea);

  return copied;
}

function JsonPreview({ title, value }: { title: string; value: JsonValue }) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");

  if (!value) {
    return null;
  }

  const formattedJson = JSON.stringify(value, null, 2);

  const copyJson = async () => {
    try {
      await navigator.clipboard.writeText(formattedJson);
      setCopyState("copied");
    } catch {
      const fallbackCopied = fallbackCopyText(formattedJson);
      setCopyState(fallbackCopied ? "copied" : "error");
    }

    window.setTimeout(() => setCopyState("idle"), 1600);
  };

  return (
    <section className="json-preview">
      <div className="json-preview-header">
        <h3>{title}</h3>
        <button
          className={
            copyState === "error" ? "json-copy-button copy-error" : "json-copy-button"
          }
          type="button"
          onClick={copyJson}
        >
          {copyState === "copied"
            ? "Copied!"
            : copyState === "error"
              ? "Copy failed"
              : "Copy JSON"}
        </button>
      </div>
      <pre>
        <code>{formattedJson}</code>
      </pre>
    </section>
  );
}

function App() {
  const [selectedTenant, setSelectedTenant] = useState("bank_demo");
  const [activeTab, setActiveTab] = useState("Chat Demo");
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");
  const [chatSessionId, setChatSessionId] = useState("");
  const [chatMessage, setChatMessage] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState("");
  const [chatResult, setChatResult] = useState<ChatResponse | null>(null);
  const chatHistoryRef = useRef<HTMLDivElement | null>(null);
  const [emailForm, setEmailForm] = useState<EmailFormState>({
    message_id: "",
    from_email: "",
    to_email: "",
    subject: "",
    body: "",
  });
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailError, setEmailError] = useState("");
  const [emailResult, setEmailResult] = useState<EmailIngestResponse | null>(null);
  const [usageLoading, setUsageLoading] = useState(false);
  const [usageError, setUsageError] = useState("");
  const [usageSummary, setUsageSummary] = useState<UsageSummaryResponse | null>(null);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [tenantsLoading, setTenantsLoading] = useState(true);
  const [tenantsError, setTenantsError] = useState("");
  const [tenantForm, setTenantForm] = useState<TenantFormState>({
    tenant_id: "",
    display_name: "",
    jira_project_key: "",
    jira_issue_type: "Incident",
  });
  const [tenantCreateLoading, setTenantCreateLoading] = useState(false);
  const [tenantCreateError, setTenantCreateError] = useState("");
  const [tenantCreateSuccess, setTenantCreateSuccess] = useState("");
  const [labelForm, setLabelForm] = useState<LabelMappingFormState>({
    label_map: "{}",
  });
  const [labelLoading, setLabelLoading] = useState(false);
  const [labelSaving, setLabelSaving] = useState(false);
  const [labelError, setLabelError] = useState("");
  const [labelSuccess, setLabelSuccess] = useState("");

  const updateEmailField = (field: keyof EmailFormState, value: string) => {
    setEmailForm((current) => ({ ...current, [field]: value }));
  };

  const updateTenantField = (field: keyof TenantFormState, value: string) => {
    setTenantForm((current) => ({ ...current, [field]: value }));
  };

  const updateLabelField = (field: keyof LabelMappingFormState, value: string) => {
    setLabelForm((current) => ({ ...current, [field]: value }));
  };

  const checkBackendHealth = async () => {
    setBackendStatus("checking");

    try {
      const response = await fetch(`${API_BASE_URL}/health`);

      if (!response.ok) {
        throw new Error("Health check failed");
      }

      const data = (await response.json()) as HealthResponse;
      setBackendStatus(data.status === "ok" ? "connected" : "offline");
    } catch {
      setBackendStatus("offline");
    }
  };

  const useSampleVpnEmail = () => {
    setEmailError("");
    setEmailResult(null);
    setEmailForm({
      message_id: `sample-vpn-${Date.now()}`,
      from_email: "employee@example.com",
      to_email: "support@example.com",
      subject: "VPN connection error",
      body:
        "I cannot connect to the VPN from Windows using AnyConnect. It fails with error 619 after I enter my password.",
    });
  };

  const useSamplePasswordResetEmail = () => {
    setEmailError("");
    setEmailResult(null);
    setEmailForm({
      message_id: `sample-password-${Date.now()}`,
      from_email: "employee@example.com",
      to_email: "support@example.com",
      subject: "Account access issue",
      body:
        "I cannot log in to my work account this morning. It says my password expired and my account is locked. Please help me reset access.",
    });
  };

  const useSampleOutlookEmail = () => {
    setEmailError("");
    setEmailResult(null);
    setEmailForm({
      message_id: `sample-outlook-${Date.now()}`,
      from_email: "employee@example.com",
      to_email: "support@example.com",
      subject: "Outlook calendar sync issue",
      body:
        "My Outlook calendar is not syncing with Exchange. Meeting invite updates are delayed and the shared mailbox also seems out of sync.",
    });
  };

  const clearEmailForm = () => {
    setEmailError("");
    setEmailResult(null);
    setEmailForm({
      message_id: "",
      from_email: "",
      to_email: "",
      subject: "",
      body: "",
    });
  };

  const submitEmailIngest = async (event: React.SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    setEmailLoading(true);
    setEmailError("");
    setEmailResult(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/email/ingest`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Company-Id": selectedTenant,
        },
        body: JSON.stringify(emailForm),
      });

      if (!response.ok) {
        throw new Error("Email ingest request failed");
      }

      const data = (await response.json()) as EmailIngestResponse;
      setEmailResult(data);
    } catch {
      setEmailError("Could not submit email ingest request");
    } finally {
      setEmailLoading(false);
    }
  };

  const resetChatSession = () => {
    setChatSessionId("");
    setChatMessage("");
    setChatMessages([]);
    setChatError("");
    setChatResult(null);
  };

  const submitChatMessage = async (event: React.SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = chatMessage.trim();

    if (!message) {
      return;
    }

    setChatLoading(true);
    setChatError("");
    setChatMessage("");
    setChatMessages((current) => [...current, { role: "user", message }]);

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Company-Id": selectedTenant,
        },
        body: JSON.stringify({
          session_id: chatSessionId || undefined,
          message,
          company_id: selectedTenant,
        }),
      });

      if (!response.ok) {
        throw new Error("Chat request failed");
      }

      const data = (await response.json()) as ChatResponse;
      setChatSessionId(data.session_id);
      setChatResult(data);
      setChatMessages((current) => [
        ...current,
        { role: "assistant", message: data.reply },
      ]);
    } catch {
      setChatError("Could not send chat message");
    } finally {
      setChatLoading(false);
    }
  };

  const loadUsageSummary = async () => {
    setUsageLoading(true);
    setUsageError("");

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/usage/summary?tenant_id=${encodeURIComponent(
          selectedTenant,
        )}`,
      );

      if (!response.ok) {
        throw new Error("Usage summary request failed");
      }

      const data = (await response.json()) as UsageSummaryResponse;
      setUsageSummary(data);
    } catch {
      setUsageError("Could not load usage summary");
    } finally {
      setUsageLoading(false);
    }
  };

  const loadTenants = async () => {
    setTenantsLoading(true);
    setTenantsError("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/tenants`);

      if (!response.ok) {
        throw new Error("Tenant request failed");
      }

      const data = (await response.json()) as TenantsResponse;
      const loadedTenants = Array.isArray(data.tenants) ? data.tenants : [];

      setTenants(loadedTenants);
      setSelectedTenant((current) => {
        if (loadedTenants.some((tenant) => tenant.tenant_id === current)) {
          return current;
        }

        return loadedTenants[0]?.tenant_id ?? "";
      });
    } catch {
      setTenants([]);
      setTenantsError("Could not load tenants");
    } finally {
      setTenantsLoading(false);
    }
  };

  const submitTenant = async (event: React.SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    setTenantCreateLoading(true);
    setTenantCreateError("");
    setTenantCreateSuccess("");

    const tenantPayload = {
      ...tenantForm,
      jira_project_key: tenantForm.jira_project_key.trim().toUpperCase(),
      jira_issue_type: "Incident",
    };

    try {
      const response = await fetch(`${API_BASE_URL}/api/tenants`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(tenantPayload),
      });

      if (!response.ok) {
        throw new Error("Tenant creation request failed");
      }

      const data = (await response.json()) as TenantCreateResponse;
      await loadTenants();
      setSelectedTenant(data.tenant_id);
      setTenantCreateSuccess(`Tenant ${data.tenant_id} is ready.`);
    } catch {
      setTenantCreateError("Could not create tenant");
    } finally {
      setTenantCreateLoading(false);
    }
  };

  const loadTenantLabels = async () => {
    if (!selectedTenant) {
      return;
    }

    setLabelLoading(true);
    setLabelError("");
    setLabelSuccess("");

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/tenants/${encodeURIComponent(selectedTenant)}/labels`,
      );

      if (!response.ok) {
        throw new Error("Tenant labels request failed");
      }

      const data = (await response.json()) as TenantLabelConfigResponse;
      setLabelForm({
        label_map: labelMapToText(data.label_map),
      });
    } catch {
      setLabelError("Could not load label mapping");
    } finally {
      setLabelLoading(false);
    }
  };

  const saveTenantLabels = async (event: React.SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!selectedTenant) {
      setLabelError("Select a tenant before saving labels");
      return;
    }

    setLabelSaving(true);
    setLabelError("");
    setLabelSuccess("");

    try {
      const labelMap = parseLabelMapJson(labelForm.label_map);
      const response = await fetch(
        `${API_BASE_URL}/api/tenants/${encodeURIComponent(selectedTenant)}/labels`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            label_map: labelMap,
          }),
        },
      );

      if (!response.ok) {
        throw new Error("Tenant labels update failed");
      }

      const data = (await response.json()) as TenantLabelConfigResponse;
      setLabelForm({
        label_map: labelMapToText(data.label_map),
      });
      setLabelSuccess("Label mapping saved.");
    } catch (error) {
      setLabelError(
        error instanceof SyntaxError ? "Label map JSON is invalid" : "Could not save label mapping",
      );
    } finally {
      setLabelSaving(false);
    }
  };

  useEffect(() => {
    void checkBackendHealth();
    void loadTenants();
  }, []);

  useEffect(() => {
    if (activeTab === "Usage") {
      void loadUsageSummary();
    }
  }, [activeTab, selectedTenant]);

  useEffect(() => {
    if (activeTab === "Label Mapping") {
      void loadTenantLabels();
    }
  }, [activeTab, selectedTenant]);

  useEffect(() => {
    if (activeTab === "Chat Demo") {
      chatHistoryRef.current?.scrollTo({ top: chatHistoryRef.current.scrollHeight });
    }
  }, [activeTab, chatMessages]);

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Deterministic IT Support Automation</p>
          <h1>Chatbox Support Demo</h1>
          <p className="lede">
            A small frontend shell for demonstrating the FastAPI backend, tenant routing,
            deterministic workflows, and Jira-style payload previews.
          </p>
        </div>

        <div className="status-panel" aria-label="Backend health status">
          <span className={`status-dot ${backendStatus}`} />
          <div>
            <span className="status-label">Backend status</span>
            <strong>
              {backendStatus === "connected"
                ? "Connected"
                : backendStatus === "offline"
                  ? "Offline"
                  : "Checking..."}
            </strong>
          </div>
        </div>
      </header>

      <section className="toolbar" aria-label="Demo controls">
        <label className="field">
          <span>Tenant</span>
          <select
            value={selectedTenant}
            onChange={(event) => setSelectedTenant(event.target.value)}
            disabled={tenantsLoading || tenants.length === 0}
          >
            {tenantsLoading ? (
              <option value="">Loading tenants...</option>
            ) : tenants.length ? (
              tenants.map((tenant) => (
                <option key={tenant.tenant_id} value={tenant.tenant_id}>
                  {tenant.tenant_id} - {tenant.display_name}
                </option>
              ))
            ) : (
              <option value="">No tenants available</option>
            )}
          </select>
          {tenantsError ? <span className="field-error">{tenantsError}</span> : null}
        </label>

        <div className="tabs" role="tablist" aria-label="Demo sections">
          {tabs.map((tab) => (
            <button
              key={tab}
              className={activeTab === tab ? "tab active" : "tab"}
              type="button"
              role="tab"
              aria-selected={activeTab === tab}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </div>
      </section>

      <section className="content-grid">
        <article className="demo-panel">
          {activeTab === "Chat Demo" ? (
            <>
              <div className="panel-heading panel-heading-row">
                <div>
                  <p className="eyebrow">Support Chat</p>
                  <h2>Chat Demo</h2>
                </div>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={resetChatSession}
                  disabled={chatLoading}
                >
                  New Session
                </button>
              </div>

              <div className="chat-history" ref={chatHistoryRef} aria-live="polite">
                {chatMessages.length ? (
                  chatMessages.map((item, index) => (
                    <div key={`${item.role}-${index}`} className={`chat-message ${item.role}`}>
                      <span>{item.role === "user" ? "You" : "Assistant"}</span>
                      <p>{item.message}</p>
                    </div>
                  ))
                ) : (
                  <p className="empty-state">
                    Send a support message to start a backend session.
                  </p>
                )}
              </div>

              {chatResult?.handoff ? (
                <div className="handoff-banner">
                  Handoff returned by backend. This session is ready for escalation.
                </div>
              ) : null}

              <form className="chat-form" onSubmit={submitChatMessage}>
                <label className="field">
                  <span>Message</span>
                  <textarea
                    rows={3}
                    value={chatMessage}
                    onChange={(event) => setChatMessage(event.target.value)}
                    placeholder="VPN is not working"
                  />
                </label>

                {chatError ? <p className="form-error">{chatError}</p> : null}

                <button className="submit-button" type="submit" disabled={chatLoading}>
                  {chatLoading ? "Sending..." : "Send Message"}
                </button>
              </form>
            </>
          ) : activeTab === "Email Ingest" ? (
            <>
              <div className="panel-heading panel-heading-row">
                <div>
                  <p className="eyebrow">Email Automation</p>
                  <h2>Email Ingest Demo</h2>
                </div>
                <div className="button-row">
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={useSampleVpnEmail}
                    disabled={emailLoading}
                  >
                    Use sample VPN email
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={useSamplePasswordResetEmail}
                    disabled={emailLoading}
                  >
                    Use sample Password Reset email
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={useSampleOutlookEmail}
                    disabled={emailLoading}
                  >
                    Use sample Outlook Email issue
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={clearEmailForm}
                    disabled={emailLoading}
                  >
                    Clear form
                  </button>
                </div>
              </div>

              <form className="email-form" onSubmit={submitEmailIngest}>
                <div className="form-grid">
                  <label className="field">
                    <span>Message ID</span>
                    <input
                      required
                      value={emailForm.message_id}
                      onChange={(event) => updateEmailField("message_id", event.target.value)}
                      placeholder="email-vpn-001"
                    />
                  </label>

                  <label className="field">
                    <span>From email</span>
                    <input
                      required
                      type="email"
                      value={emailForm.from_email}
                      onChange={(event) => updateEmailField("from_email", event.target.value)}
                      placeholder="employee@example.com"
                    />
                  </label>
                </div>

                <label className="field">
                  <span>To email</span>
                  <input
                    required
                    type="email"
                    value={emailForm.to_email}
                    onChange={(event) => updateEmailField("to_email", event.target.value)}
                    placeholder="support@example.com"
                  />
                </label>

                <label className="field">
                  <span>Subject</span>
                  <input
                    value={emailForm.subject}
                    onChange={(event) => updateEmailField("subject", event.target.value)}
                    placeholder="VPN issue"
                  />
                </label>

                <label className="field">
                  <span>Body</span>
                  <textarea
                    rows={6}
                    value={emailForm.body}
                    onChange={(event) => updateEmailField("body", event.target.value)}
                    placeholder="I cannot connect to VPN from Windows using AnyConnect. Error 619."
                  />
                </label>

                {emailError ? <p className="form-error">{emailError}</p> : null}

                <p className="form-note">
                  Submitting sample emails records demo activities for the selected tenant.
                </p>

                <button className="submit-button" type="submit" disabled={emailLoading}>
                  {emailLoading ? "Submitting..." : "Submit Email"}
                </button>
              </form>
            </>
          ) : activeTab === "Usage" ? (
            <>
              <div className="panel-heading panel-heading-row">
                <div>
                  <p className="eyebrow">Usage Tracking</p>
                  <h2>Usage Summary</h2>
                </div>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={loadUsageSummary}
                  disabled={usageLoading}
                >
                  {usageLoading ? "Refreshing..." : "Refresh"}
                </button>
              </div>

              {usageError ? <p className="form-error">{usageError}</p> : null}

              <div className="usage-grid">
                <section className="usage-card">
                  <span>Tenant</span>
                  <strong>{usageSummary?.tenant_id ?? selectedTenant}</strong>
                </section>
                <section className="usage-card">
                  <span>Total activities</span>
                  <strong>{usageSummary?.total ?? 0}</strong>
                </section>
              </div>

              <section className="usage-breakdown">
                <h3>Breakdown by event type</h3>
                {usageSummary && Object.keys(usageSummary.by_event_type).length ? (
                  <dl>
                    {Object.entries(usageSummary.by_event_type).map(([eventType, count]) => (
                      <div key={eventType}>
                        <dt>{eventType}</dt>
                        <dd>{count}</dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p className="empty-state">
                    {usageLoading ? "Loading usage summary..." : "No activity events yet."}
                  </p>
                )}
              </section>

              {usageSummary?.by_intent ? (
                <section className="usage-breakdown">
                  <h3>Breakdown by intent</h3>
                  {Object.keys(usageSummary.by_intent).length ? (
                    <dl>
                      {Object.entries(usageSummary.by_intent).map(([intent, count]) => (
                        <div key={intent}>
                          <dt>{intent}</dt>
                          <dd>{count}</dd>
                        </div>
                      ))}
                    </dl>
                  ) : (
                    <p className="empty-state">No intent activity yet.</p>
                  )}
                </section>
              ) : null}
            </>
          ) : activeTab === "Add Tenant" ? (
            <>
              <div className="panel-heading">
                <p className="eyebrow">Tenant Setup</p>
                <h2>Tenant Management</h2>
              </div>

              <form className="tenant-form" onSubmit={submitTenant}>
                <div className="form-grid">
                  <label className="field">
                    <span>Tenant ID</span>
                    <input
                      required
                      value={tenantForm.tenant_id}
                      onChange={(event) => updateTenantField("tenant_id", event.target.value)}
                      placeholder="acme_support"
                    />
                  </label>

                  <label className="field">
                    <span>Display name</span>
                    <input
                      required
                      value={tenantForm.display_name}
                      onChange={(event) => updateTenantField("display_name", event.target.value)}
                      placeholder="Acme Support"
                    />
                  </label>
                </div>

                <div className="form-grid">
                  <label className="field">
                    <span>Jira project key (UPPERCASE)</span>
                    <input
                      required
                      value={tenantForm.jira_project_key}
                      onChange={(event) =>
                        updateTenantField("jira_project_key", event.target.value.toUpperCase())
                      }
                      placeholder="ACME"
                    />
                  </label>
                </div>

                <button className="submit-button" type="submit" disabled={tenantCreateLoading}>
                  {tenantCreateLoading ? "Creating..." : "Create Tenant"}
                </button>

                {tenantCreateError ? <p className="form-error">{tenantCreateError}</p> : null}
                {tenantCreateSuccess ? (
                  <p className="form-success">{tenantCreateSuccess}</p>
                ) : null}
              </form>
            </>
          ) : activeTab === "Label Mapping" ? (
            <>
              <div className="panel-heading panel-heading-row">
                <div>
                  <p className="eyebrow">Tenant Labels</p>
                  <h2>Label Mapping</h2>
                </div>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={loadTenantLabels}
                  disabled={labelLoading || !selectedTenant}
                >
                  {labelLoading ? "Loading..." : "Refresh"}
                </button>
              </div>

              <form className="label-form" onSubmit={saveTenantLabels}>
                <p className="form-note">System default label: it-support</p>

                <label className="field">
                  <span>Label map JSON</span>
                  <textarea
                    rows={10}
                    value={labelForm.label_map}
                    onChange={(event) => updateLabelField("label_map", event.target.value)}
                    placeholder={
                      '{\n  "vpn": ["vpn-label"],\n  "connectivity": ["connectivity-label"]\n}'
                    }
                  />
                </label>

                <button
                  className="submit-button"
                  type="submit"
                  disabled={labelSaving || labelLoading || !selectedTenant}
                >
                  {labelSaving ? "Saving..." : "Save Mapping"}
                </button>

                {labelError ? <p className="form-error">{labelError}</p> : null}
                {labelSuccess ? <p className="form-success">{labelSuccess}</p> : null}
              </form>
            </>
          ) : null}
        </article>

        <aside className="result-panel">
          <section className="system-status" aria-label="System status">
            <div>
              <span>Backend</span>
              <strong>Connected</strong>
            </div>
            <div>
              <span>Redis mode</span>
              <strong>Enabled</strong>
            </div>
            <div>
              <span>LLM provider</span>
              <strong>mock</strong>
            </div>
            <div>
              <span>Workflow mode</span>
              <strong>Deterministic-first</strong>
            </div>
            <div>
              <span>Loaded tenants</span>
              <strong>{tenantsLoading ? "Loading..." : tenants.length}</strong>
            </div>
          </section>

          <div className="panel-heading">
            {activeTab === "Add Tenant" || activeTab === "Label Mapping" ? (
              <>
                <p className="eyebrow">
                  {activeTab === "Label Mapping" ? "Label Summary" : "Tenant Summary"}
                </p>
                <h2>
                  {activeTab === "Label Mapping" ? "Current Mapping State" : "Current Tenant State"}
                </h2>
              </>
            ) : (
              <>
                <p className="eyebrow">Result Preview</p>
                <h2>Response Metadata</h2>
              </>
            )}
          </div>
          {activeTab === "Chat Demo" ? (
            <dl>
              <div>
                <dt>Session ID</dt>
                <dd>{chatSessionId || "Not started"}</dd>
              </div>
              <div>
                <dt>Intent</dt>
                <dd>{chatResult?.intent ?? "Not available"}</dd>
              </div>
              <div>
                <dt>Confidence</dt>
                <dd>
                  {chatResult ? `${Math.round(chatResult.confidence * 100)}%` : "Not available"}
                </dd>
              </div>
              <div>
                <dt>Handoff</dt>
                <dd>{chatResult ? (chatResult.handoff ? "Yes" : "No") : "Not available"}</dd>
              </div>
              <div className="metadata-wide">
                <JsonPreview title="Handoff Summary" value={chatResult?.handoff_summary} />
              </div>
              <div className="metadata-wide">
                <JsonPreview title="Jira Payload Preview" value={chatResult?.jira_payload_preview} />
              </div>
            </dl>
          ) : activeTab === "Email Ingest" ? (
            <dl>
              <div>
                <dt>Intent</dt>
                <dd>{emailResult?.intent ?? "Not available"}</dd>
              </div>
              <div>
                <dt>Confidence</dt>
                <dd>
                  {emailResult ? `${Math.round(emailResult.confidence * 100)}%` : "Not available"}
                </dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>{emailResult?.status ?? "Not available"}</dd>
              </div>
              <div>
                <dt>Tenant ID</dt>
                <dd>{emailResult?.tenant_id ?? "Not available"}</dd>
              </div>
              <div>
                <dt>Internal tags</dt>
                <dd className="tag-list">
                  {emailResult?.internal_tags.length
                    ? emailResult.internal_tags.map((tag) => <span key={tag}>{tag}</span>)
                    : "Waiting for a backend response"}
                </dd>
              </div>
              <div className="metadata-wide">
                <JsonPreview title="Handoff Summary" value={emailResult?.handoff_summary} />
              </div>
              <div className="metadata-wide">
                <JsonPreview title="Jira Payload Preview" value={emailResult?.jira_payload_preview} />
              </div>
            </dl>
          ) : activeTab === "Usage" ? (
            <dl>
              <div>
                <dt>Tenant ID</dt>
                <dd>{usageSummary?.tenant_id ?? selectedTenant}</dd>
              </div>
              <div>
                <dt>Total activities</dt>
                <dd>{usageLoading ? "Loading..." : usageSummary?.total ?? 0}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>{usageError || (usageSummary ? "Loaded" : "Not loaded")}</dd>
              </div>
            </dl>
          ) : activeTab === "Add Tenant" ? (
            <dl>
              <div>
                <dt>Selected tenant</dt>
                <dd>{selectedTenant || "Not selected"}</dd>
              </div>
              <div>
                <dt>Loaded tenants</dt>
                <dd>{tenantsLoading ? "Loading..." : tenants.length}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>{tenantCreateError || tenantCreateSuccess || "Ready"}</dd>
              </div>
            </dl>
          ) : (
            <dl>
              <div>
                <dt>Selected tenant</dt>
                <dd>{selectedTenant || "Not selected"}</dd>
              </div>
              <div>
                <dt>System default label</dt>
                <dd>it-support</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>
                  {labelLoading
                    ? "Loading..."
                    : labelSaving
                      ? "Saving..."
                      : labelError || labelSuccess || "Ready"}
                </dd>
              </div>
            </dl>
          )}
        </aside>
      </section>
    </main>
  );
}

export default App;

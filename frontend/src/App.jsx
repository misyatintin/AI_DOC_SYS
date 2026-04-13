import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock3,
  Eye,
  FileText,
  LoaderCircle,
  PencilLine,
  RefreshCw,
  Save,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  XCircle,
} from 'lucide-react';
import { startTransition, useDeferredValue, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import './App.css';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api';

const emptyInvoice = {
  vendor_name: '',
  invoice_number: '',
  invoice_date: '',
  currency: '',
  total_amount: '',
  tax_amount: '',
  line_items: [{ description: '', quantity: 0, unit_price: 0, line_total: 0 }],
};

const emptyPrompt = {
  id: null,
  version: '',
  prompt_text: '',
  is_active: false,
};

function App() {
  const [documents, setDocuments] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [prompts, setPrompts] = useState([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState(null);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [selectedPromptId, setSelectedPromptId] = useState(null);
  const [promptEditor, setPromptEditor] = useState(emptyPrompt);
  const [isCreatingPrompt, setIsCreatingPrompt] = useState(false);
  const [editState, setEditState] = useState(emptyInvoice);
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState('');
  const [loadingPdfPreview, setLoadingPdfPreview] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [savingCorrection, setSavingCorrection] = useState(false);
  const [savingPrompt, setSavingPrompt] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [message, setMessage] = useState('');
  const [messageTone, setMessageTone] = useState('success');

  const deferredSearch = useDeferredValue(searchTerm);

  useEffect(() => {
    void hydrate();
  }, []);

  useEffect(() => {
    if (!selectedDocumentId) {
      setSelectedDocument(null);
      setEditState(emptyInvoice);
      setPdfPreviewUrl('');
      return;
    }
    void fetchDocument(selectedDocumentId);
  }, [selectedDocumentId]);

  useEffect(() => {
    if (isCreatingPrompt) {
      return;
    }

    if (!prompts.length) {
      setSelectedPromptId(null);
      setPromptEditor(emptyPrompt);
      return;
    }

    const nextPrompt =
      prompts.find((prompt) => prompt.id === selectedPromptId) ??
      prompts.find((prompt) => prompt.is_active) ??
      prompts[0];

    setSelectedPromptId(nextPrompt.id);
    setPromptEditor(nextPrompt);
  }, [isCreatingPrompt, prompts, selectedPromptId]);

  useEffect(() => {
    let revokedUrl = '';

    async function loadPreview() {
      if (!selectedDocument) {
        setPdfPreviewUrl('');
        return;
      }

      setLoadingPdfPreview(true);
      try {
        const response = await axios.get(`${API_BASE}/documents/${selectedDocument.id}/file`, {
          responseType: 'blob',
        });
        revokedUrl = URL.createObjectURL(response.data);
        setPdfPreviewUrl(revokedUrl);
      } catch {
        setPdfPreviewUrl('');
        showMessage('Unable to load PDF preview for this document.', 'error');
      } finally {
        setLoadingPdfPreview(false);
      }
    }

    void loadPreview();

    return () => {
      if (revokedUrl) {
        URL.revokeObjectURL(revokedUrl);
      }
    };
  }, [selectedDocument]);

  async function hydrate(preferredDocumentId = null) {
    const [documentsResponse, metricsResponse, promptsResponse] = await Promise.all([
      axios.get(`${API_BASE}/documents`),
      axios.get(`${API_BASE}/metrics/overview`),
      axios.get(`${API_BASE}/prompts`),
    ]);

    const nextDocuments = documentsResponse.data;
    const nextPrompts = promptsResponse.data;

    startTransition(() => {
      setDocuments(nextDocuments);
      setMetrics(metricsResponse.data);
      setPrompts(nextPrompts);
    });

    if (!nextDocuments.length) {
      setSelectedDocumentId(null);
      return;
    }

    const desiredId =
      preferredDocumentId && nextDocuments.some((document) => document.id === preferredDocumentId)
        ? preferredDocumentId
        : selectedDocumentId && nextDocuments.some((document) => document.id === selectedDocumentId)
          ? selectedDocumentId
          : nextDocuments[0].id;

    if (desiredId !== selectedDocumentId) {
      setSelectedDocumentId(desiredId);
    } else if (desiredId) {
      await fetchDocument(desiredId);
    }
  }

  async function fetchDocument(documentId) {
    setLoadingDetail(true);
    try {
      const response = await axios.get(`${API_BASE}/documents/${documentId}`);
      setSelectedDocument(response.data);
      syncEditState(response.data);
    } finally {
      setLoadingDetail(false);
    }
  }

  function syncEditState(document) {
    const structuredData = document?.extraction?.structured_data;
    setEditState({
      vendor_name: structuredData?.vendor_name ?? '',
      invoice_number: structuredData?.invoice_number ?? '',
      invoice_date: structuredData?.invoice_date ?? '',
      currency: structuredData?.currency ?? '',
      total_amount: structuredData?.total_amount ?? '',
      tax_amount: structuredData?.tax_amount ?? '',
      line_items: structuredData?.line_items?.length
        ? structuredData.line_items
        : [{ description: '', quantity: 0, unit_price: 0, line_total: 0 }],
    });
  }

  async function handleUpload(event) {
    const files = Array.from(event.target.files || []);
    if (!files.length) {
      return;
    }

    setUploading(true);
    try {
      if (files.length === 1) {
        const formData = new FormData();
        formData.append('file', files[0]);
        const response = await axios.post(`${API_BASE}/documents`, formData);
        await hydrate(response.data.id);
      } else {
        const formData = new FormData();
        files.forEach((file) => formData.append('files', file));
        const response = await axios.post(`${API_BASE}/documents/bulk`, formData);
        await hydrate(response.data[0]?.id ?? null);
      }
      showMessage('Upload completed and documents processed.', 'success');
      event.target.value = '';
    } catch {
      showMessage('Upload failed. Please check the backend logs and try again.', 'error');
    } finally {
      setUploading(false);
    }
  }

  async function handleCorrectionSave() {
    if (!selectedDocument) {
      return;
    }
    setSavingCorrection(true);
    try {
      await axios.patch(`${API_BASE}/documents/${selectedDocument.id}/correction`, {
        structured_data: {
          ...editState,
          total_amount: editState.total_amount === '' ? null : Number(editState.total_amount),
          tax_amount: editState.tax_amount === '' ? null : Number(editState.tax_amount),
          line_items: editState.line_items.map((item) => ({
            ...item,
            quantity: Number(item.quantity || 0),
            unit_price: Number(item.unit_price || 0),
            line_total: Number(item.line_total || 0),
          })),
        },
      });
      await hydrate(selectedDocument.id);
      showMessage('Manual corrections saved and revalidated.', 'success');
    } catch {
      showMessage('Unable to save corrections.', 'error');
    } finally {
      setSavingCorrection(false);
    }
  }

  async function handleReprocess(documentId) {
    try {
      await axios.post(`${API_BASE}/reprocess/${documentId}`);
      await hydrate(documentId);
      showMessage('Document reprocessed with the active prompt.', 'success');
    } catch {
      showMessage('Reprocess failed.', 'error');
    }
  }

  async function handleDelete(documentId) {
    if (!window.confirm('Delete this uploaded invoice and its extracted data?')) {
      return;
    }

    try {
      await axios.delete(`${API_BASE}/documents/${documentId}`);
      const nextId = documents.find((document) => document.id !== documentId)?.id ?? null;
      await hydrate(nextId);
      showMessage('Document deleted successfully.', 'success');
    } catch {
      showMessage('Unable to delete the document.', 'error');
    }
  }

  async function handlePromptSave(event) {
    event.preventDefault();
    if (!promptEditor.version.trim() || !promptEditor.prompt_text.trim()) {
      showMessage('Prompt version and prompt text are required.', 'error');
      return;
    }

    setSavingPrompt(true);
    try {
      if (promptEditor.id) {
        await axios.put(`${API_BASE}/prompts/${promptEditor.id}`, {
          version: promptEditor.version,
          prompt_text: promptEditor.prompt_text,
        });
        showMessage('Prompt updated successfully.', 'success');
      } else {
        const response = await axios.post(`${API_BASE}/prompts`, {
          version: promptEditor.version,
          prompt_text: promptEditor.prompt_text,
        });
        setIsCreatingPrompt(false);
        setSelectedPromptId(response.data.id);
        showMessage('Prompt version created and activated.', 'success');
      }
      await hydrate(selectedDocumentId);
    } catch {
      showMessage('Unable to save the prompt version.', 'error');
    } finally {
      setSavingPrompt(false);
    }
  }

  async function handlePromptActivate() {
    if (!promptEditor.id) {
      return;
    }

    try {
      await axios.post(`${API_BASE}/prompts/${promptEditor.id}/activate`);
      await hydrate(selectedDocumentId);
      showMessage('Prompt activated. Reprocess documents to apply it.', 'success');
    } catch {
      showMessage('Unable to activate the selected prompt.', 'error');
    }
  }

  function showMessage(text, tone) {
    setMessage(text);
    setMessageTone(tone);
  }

  const filteredDocuments = useMemo(() => {
    return documents.filter((document) => {
      const matchesStatus = statusFilter === 'all' || document.status === statusFilter;
      const matchesSearch =
        deferredSearch.trim() === '' ||
        document.filename.toLowerCase().includes(deferredSearch.toLowerCase()) ||
        String(document.id).includes(deferredSearch);
      return matchesStatus && matchesSearch;
    });
  }, [deferredSearch, documents, statusFilter]);

  const processingTrend = useMemo(() => {
    return [...documents]
      .slice(0, 8)
      .reverse()
      .map((document) => ({
        name: `#${document.id}`,
        confidence: Math.round((document.extraction?.confidence_score ?? 0) * 100),
        latency: document.extraction?.processing_time_ms ?? 0,
      }));
  }, [documents]);

  const statusBreakdown = useMemo(() => {
    const counts = documents.reduce(
      (accumulator, document) => {
        accumulator[document.status] = (accumulator[document.status] ?? 0) + 1;
        return accumulator;
      },
      { completed: 0, review_required: 0, failed: 0, processing: 0, pending: 0 },
    );
    return [
      { name: 'Completed', value: counts.completed, color: '#127a4b' },
      { name: 'Review', value: counts.review_required, color: '#d18b1f' },
      { name: 'Failed', value: counts.failed, color: '#c0392b' },
      { name: 'In Flight', value: counts.processing + counts.pending, color: '#116f7a' },
    ].filter((entry) => entry.value > 0);
  }, [documents]);

  const validationErrors = selectedDocument?.extraction?.validation_errors ?? [];
  const missingFields = selectedDocument?.extraction?.missing_fields ?? [];
  const pdfUrl = selectedDocument ? `${API_BASE}/documents/${selectedDocument.id}/file` : null;
  const activePrompt = prompts.find((prompt) => prompt.is_active);

  return (
    <div className="app-shell">
      <aside className="side-panel">
        <div className="brand-block">
          <div className="brand-mark">AI</div>
          <div>
            <p className="eyebrow">Document Intelligence</p>
            <h1>Invoice Review Workspace</h1>
          </div>
        </div>

        <section className="upload-card">
          <div>
            <p className="section-kicker">Upload</p>
            <h2>Single or bulk PDF ingestion</h2>
          </div>
          <label className="upload-zone">
            <Upload size={18} />
            <span>{uploading ? 'Processing uploads...' : 'Upload invoice PDFs'}</span>
            <input type="file" multiple accept="application/pdf" hidden onChange={handleUpload} />
          </label>
          <p className="helper-text">
            Original PDFs are stored and kept available for side-by-side human verification.
          </p>
        </section>

        <section className="prompt-card">
          <div className="card-heading">
            <Sparkles size={18} />
            <div>
              <p className="section-kicker">Prompt Management</p>
              <h3>Version, edit, and activate prompts</h3>
            </div>
          </div>

          <div className="prompt-list">
            {prompts.map((prompt) => (
              <button
                key={prompt.id}
                type="button"
                className={`prompt-pill ${prompt.is_active ? 'active' : ''} ${selectedPromptId === prompt.id ? 'selected' : ''}`}
                  onClick={() => {
                    setIsCreatingPrompt(false);
                    setSelectedPromptId(prompt.id);
                    setPromptEditor(prompt);
                  }}
                >
                <strong>{prompt.version}</strong>
                <span>{prompt.is_active ? 'Active' : 'Inactive'}</span>
              </button>
            ))}
          </div>

          <div className="prompt-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                setIsCreatingPrompt(true);
                setSelectedPromptId(-1);
                setPromptEditor({
                  id: null,
                  version: '',
                  prompt_text: '',
                  is_active: false,
                });
              }}
            >
              New version
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={handlePromptActivate}
              disabled={!promptEditor.id || promptEditor.is_active}
            >
              Activate selected
            </button>
          </div>

          <form className="prompt-form" onSubmit={handlePromptSave}>
            <input
              value={promptEditor.version}
              onChange={(event) => setPromptEditor((current) => ({ ...current, version: event.target.value }))}
              placeholder="v2.1-enterprise"
            />
            <textarea
              value={promptEditor.prompt_text}
              onChange={(event) => setPromptEditor((current) => ({ ...current, prompt_text: event.target.value }))}
              rows={8}
              placeholder="Prompt content used by the LLM extraction pipeline."
            />
            <button type="submit" disabled={savingPrompt}>
              {savingPrompt ? 'Saving...' : promptEditor.id ? 'Update prompt' : 'Create prompt'}
            </button>
          </form>
        </section>
      </aside>

      <main className="main-panel">
        <section className="hero">
          <div>
            <p className="eyebrow">Operations Overview</p>
            <h2>Review invoices with the source PDF and extracted data in one place.</h2>
          </div>
          <div className="hero-actions">
            <div className="hero-badge">
              <ShieldCheck size={16} />
              Active prompt {activePrompt?.version ?? 'not set'}
            </div>
            <button className="secondary-button" onClick={() => hydrate(selectedDocumentId)}>
              Refresh workspace
            </button>
          </div>
        </section>

        {message ? <div className={`message-banner ${messageTone}`}>{message}</div> : null}

        <section className="metric-grid">
          <MetricCard
            icon={<FileText size={18} />}
            label="Processed invoices"
            value={metrics?.total_documents ?? 0}
            tone="neutral"
          />
          <MetricCard
            icon={<CheckCircle2 size={18} />}
            label="Extraction success rate"
            value={`${metrics?.extraction_success_rate ?? 0}%`}
            tone="success"
          />
          <MetricCard
            icon={<Clock3 size={18} />}
            label="Average processing time"
            value={`${metrics?.average_processing_time_ms ?? 0} ms`}
            tone="teal"
          />
          <MetricCard
            icon={<AlertTriangle size={18} />}
            label="Manual review required"
            value={metrics?.manual_review_required ?? 0}
            tone="warning"
          />
        </section>

        <section className="analytics-grid">
          <article className="panel-card chart-card">
            <div className="panel-header">
              <div>
                <p className="section-kicker">Monitoring</p>
                <h3>Confidence trend across recent documents</h3>
              </div>
              <BarChart3 size={18} />
            </div>
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={processingTrend}>
                <defs>
                  <linearGradient id="confidenceFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#0f766e" stopOpacity={0.68} />
                    <stop offset="100%" stopColor="#0f766e" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#dbe4df" strokeDasharray="4 4" vertical={false} />
                <XAxis dataKey="name" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} />
                <Tooltip />
                <Area type="monotone" dataKey="confidence" stroke="#0f766e" fill="url(#confidenceFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </article>

          <article className="panel-card chart-card">
            <div className="panel-header">
              <div>
                <p className="section-kicker">Error Report</p>
                <h3>Queue status distribution</h3>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={statusBreakdown} dataKey="value" nameKey="name" innerRadius={58} outerRadius={90}>
                  {statusBreakdown.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            <div className="status-legend">
              {statusBreakdown.map((entry) => (
                <div key={entry.name} className="legend-item">
                  <span className="legend-dot" style={{ backgroundColor: entry.color }} />
                  {entry.name}: {entry.value}
                </div>
              ))}
            </div>
          </article>
        </section>

        <section className="workspace-grid">
          <article className="panel-card queue-card">
            <div className="panel-header">
              <div>
                <p className="section-kicker">Processed Invoices</p>
                <h3>Select a document to review</h3>
              </div>
            </div>

            <div className="toolbar">
              <label className="search-field">
                <Search size={16} />
                <input
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="Search by filename or id"
                />
              </label>
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="all">All states</option>
                <option value="completed">Completed</option>
                <option value="review_required">Needs review</option>
                <option value="failed">Failed</option>
                <option value="processing">Processing</option>
                <option value="pending">Pending</option>
              </select>
            </div>

            <div className="document-list">
              {filteredDocuments.map((document) => (
                <button
                  type="button"
                  key={document.id}
                  className={`document-row ${selectedDocumentId === document.id ? 'selected' : ''}`}
                  onClick={() => setSelectedDocumentId(document.id)}
                >
                  <div className="document-row-main">
                    <strong>{document.filename}</strong>
                    <p>Invoice #{document.id}</p>
                  </div>
                  <div className="document-row-meta">
                    <StatusBadge status={document.status} />
                    <span>{Math.round((document.extraction?.confidence_score ?? 0) * 100)}%</span>
                  </div>
                </button>
              ))}
              {!filteredDocuments.length && <p className="empty-state compact">No invoices match the current filters.</p>}
            </div>
          </article>

          <article className="panel-card review-card">
            <div className="panel-header">
              <div>
                <p className="section-kicker">Human Verification</p>
                <h3>Compare the PDF with extracted fields</h3>
              </div>
              {selectedDocument ? (
                <div className="review-actions">
                  <a className="secondary-button" href={pdfUrl} target="_blank" rel="noreferrer">
                    <Eye size={15} />
                    Open PDF
                  </a>
                  <button className="secondary-button" onClick={() => handleReprocess(selectedDocument.id)}>
                    <RefreshCw size={15} />
                    Reprocess
                  </button>
                  <button className="danger-button" onClick={() => handleDelete(selectedDocument.id)}>
                    <Trash2 size={15} />
                    Delete
                  </button>
                </div>
              ) : null}
            </div>

            {loadingDetail ? (
              <div className="detail-loader">
                <LoaderCircle size={22} className="spin" />
                Loading invoice detail...
              </div>
            ) : selectedDocument ? (
              <div className="review-layout">
                <section className="pdf-panel">
                  <div className="pdf-panel-header">
                    <div>
                      <p className="section-kicker">Source Document</p>
                      <h4>{selectedDocument.filename}</h4>
                    </div>
                    <span className="mini-meta">{selectedDocument.content_type || 'application/pdf'}</span>
                  </div>
                  {loadingPdfPreview ? (
                    <div className="pdf-frame pdf-placeholder">
                      <LoaderCircle size={22} className="spin" />
                      Loading PDF preview...
                    </div>
                  ) : pdfPreviewUrl ? (
                    <iframe
                      title="Invoice PDF preview"
                      src={`${pdfPreviewUrl}#toolbar=1&navpanes=0&scrollbar=1`}
                      className="pdf-frame"
                    />
                  ) : (
                    <div className="pdf-frame pdf-placeholder">
                      PDF preview is unavailable for this document.
                    </div>
                  )}
                </section>

                <section className="detail-panel">
                  <div className="detail-summary">
                    <div>
                      <p className="summary-label">Status</p>
                      <StatusBadge status={selectedDocument.status} />
                    </div>
                    <div>
                      <p className="summary-label">Confidence</p>
                      <strong>{Math.round((selectedDocument.extraction?.confidence_score ?? 0) * 100)}%</strong>
                    </div>
                    <div>
                      <p className="summary-label">Prompt version</p>
                      <strong>{selectedDocument.extraction?.prompt_version ?? 'n/a'}</strong>
                    </div>
                    <div>
                      <p className="summary-label">File size</p>
                      <strong>{selectedDocument.file_size ? `${Math.round(selectedDocument.file_size / 1024)} KB` : 'n/a'}</strong>
                    </div>
                  </div>

                  <div className="error-grid">
                    <ErrorTile
                      title="Validation errors"
                      items={validationErrors}
                      emptyLabel="No validation errors"
                      tone="error"
                      icon={<XCircle size={16} />}
                    />
                    <ErrorTile
                      title="Missing fields"
                      items={missingFields}
                      emptyLabel="Required fields are present"
                      tone="warning"
                      icon={<AlertTriangle size={16} />}
                    />
                  </div>

                  <div className="form-grid">
                    <EditableField label="Vendor name" value={editState.vendor_name} onChange={(value) => setEditState((current) => ({ ...current, vendor_name: value }))} />
                    <EditableField label="Invoice number" value={editState.invoice_number} onChange={(value) => setEditState((current) => ({ ...current, invoice_number: value }))} />
                    <EditableField label="Invoice date" value={editState.invoice_date} onChange={(value) => setEditState((current) => ({ ...current, invoice_date: value }))} />
                    <EditableField label="Currency" value={editState.currency} onChange={(value) => setEditState((current) => ({ ...current, currency: value }))} />
                    <EditableField label="Total amount" value={editState.total_amount} onChange={(value) => setEditState((current) => ({ ...current, total_amount: value }))} />
                    <EditableField label="Tax amount" value={editState.tax_amount} onChange={(value) => setEditState((current) => ({ ...current, tax_amount: value }))} />
                  </div>

                  <div className="line-items-section">
                    <div className="line-items-header">
                      <h4>Line items</h4>
                      <button
                        className="secondary-button"
                        onClick={() =>
                          setEditState((current) => ({
                            ...current,
                            line_items: [
                              ...current.line_items,
                              { description: '', quantity: 0, unit_price: 0, line_total: 0 },
                            ],
                          }))
                        }
                      >
                        Add line item
                      </button>
                    </div>

                    {editState.line_items.map((item, index) => (
                      <div className="line-item-row" key={`${selectedDocument.id}-${index}`}>
                        <input
                          value={item.description}
                          onChange={(event) => updateLineItem(index, 'description', event.target.value)}
                          placeholder="Description"
                        />
                        <input
                          value={item.quantity}
                          onChange={(event) => updateLineItem(index, 'quantity', event.target.value)}
                          placeholder="Qty"
                        />
                        <input
                          value={item.unit_price}
                          onChange={(event) => updateLineItem(index, 'unit_price', event.target.value)}
                          placeholder="Unit price"
                        />
                        <input
                          value={item.line_total}
                          onChange={(event) => updateLineItem(index, 'line_total', event.target.value)}
                          placeholder="Line total"
                        />
                        <button className="line-item-remove" onClick={() => removeLineItem(index)} type="button">
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>

                  <div className="detail-actions">
                    <button className="primary-button" onClick={handleCorrectionSave} disabled={savingCorrection}>
                      <Save size={15} />
                      {savingCorrection ? 'Saving...' : 'Save verified extraction'}
                    </button>
                  </div>
                </section>
              </div>
            ) : (
              <p className="empty-state">Upload invoices or select a document to review the PDF and extracted fields.</p>
            )}
          </article>
        </section>
      </main>
    </div>
  );

  function updateLineItem(index, field, value) {
    setEditState((current) => ({
      ...current,
      line_items: current.line_items.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [field]: value } : item,
      ),
    }));
  }

  function removeLineItem(index) {
    setEditState((current) => ({
      ...current,
      line_items:
        current.line_items.length === 1
          ? [{ description: '', quantity: 0, unit_price: 0, line_total: 0 }]
          : current.line_items.filter((_, itemIndex) => itemIndex !== index),
    }));
  }
}

function MetricCard({ icon, label, value, tone }) {
  return (
    <article className={`metric-card ${tone}`}>
      <div className="metric-icon">{icon}</div>
      <p>{label}</p>
      <strong>{value}</strong>
    </article>
  );
}

function StatusBadge({ status }) {
  return <span className={`status-badge ${status}`}>{status.replace('_', ' ')}</span>;
}

function ErrorTile({ title, items, emptyLabel, tone, icon }) {
  return (
    <div className={`error-tile ${tone}`}>
      <div className="error-tile-title">
        {icon}
        <strong>{title}</strong>
      </div>
      {items.length ? (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p>{emptyLabel}</p>
      )}
    </div>
  );
}

function EditableField({ label, value, onChange }) {
  return (
    <label className="editable-field">
      <span>{label}</span>
      <input value={value ?? ''} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

export default App;

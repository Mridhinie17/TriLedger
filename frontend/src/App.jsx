import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import InvoiceQueue from './components/InvoiceQueue';
import PdfViewerPane from './components/PdfViewerPane';
import ReconciliationMatrixPane from './components/ReconciliationMatrixPane';
import AgentDrawer from './components/AgentDrawer';
import DecisionModal from './components/DecisionModal';

export default function App() {
  // Global & Operational State
  const [stats, setStats] = useState(null);
  const [apiHealthy, setApiHealthy] = useState(false);
  const [invoices, setInvoices] = useState([]);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState(null);
  const [invoiceDetail, setInvoiceDetail] = useState(null);
  const [agentReport, setAgentReport] = useState(null);

  // Filters & Pagination
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [currencyFilter, setCurrencyFilter] = useState('ALL');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Loading & Action States
  const [isLoadingQueue, setIsLoadingQueue] = useState(false);
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isSubmittingDecision, setIsSubmittingDecision] = useState(false);

  // Modal State
  const [decisionModalOpen, setDecisionModalOpen] = useState(false);
  const [targetDecision, setTargetDecision] = useState('APPROVE');
  const [toastMessage, setToastMessage] = useState(null);

  const showToast = (msg, type = 'success') => {
    setToastMessage({ text: msg, type });
    setTimeout(() => setToastMessage(null), 4000);
  };

  // 1. Fetch Health & Global KPIs
  const fetchGlobalData = useCallback(async () => {
    try {
      const healthRes = await fetch('/health');
      if (healthRes.ok) setApiHealthy(true);

      const statsRes = await fetch('/api/stats');
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
    } catch (err) {
      console.warn('API connection check failed:', err);
      setApiHealthy(false);
    }
  }, []);

  // 2. Fetch Invoice Queue
  const fetchInvoices = useCallback(async () => {
    setIsQueueLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: '25',
      });
      if (statusFilter !== 'ALL') params.append('status', statusFilter);
      if (currencyFilter !== 'ALL') params.append('currency', currencyFilter);
      if (searchTerm.trim()) params.append('search', searchTerm.trim());

      const res = await fetch(`/api/invoices?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setInvoices(data.items);
        setTotalPages(Math.ceil(data.total / data.limit));

        // Auto-select first item if none selected or not in list
        if (data.items.length > 0 && (!selectedInvoiceId || !data.items.some(i => i.invoice_number === selectedInvoiceId))) {
          setSelectedInvoiceId(data.items[0].invoice_number);
        }
      }
    } catch (err) {
      console.error('Failed to fetch invoice queue:', err);
      showToast('Failed to load invoices from backend', 'error');
    } finally {
      setIsQueueLoading(false);
    }
  }, [page, statusFilter, currencyFilter, searchTerm, selectedInvoiceId]);

  // Alias for state setter
  const setIsQueueLoading = (val) => setIsLoadingQueue(val);

  // 3. Fetch Detail when selected invoice changes
  useEffect(() => {
    if (!selectedInvoiceId) return;

    let isMounted = true;
    async function loadDetail() {
      try {
        const res = await fetch(`/api/invoices/${selectedInvoiceId}`);
        if (res.ok) {
          const detail = await res.json();
          if (isMounted) {
            setInvoiceDetail(detail);
            setAgentReport(null); // Reset agent report for newly selected invoice
          }
        }
      } catch (err) {
        console.error('Failed to load invoice detail:', err);
      }
    }

    loadDetail();
    return () => { isMounted = false; };
  }, [selectedInvoiceId]);

  // Initial load
  useEffect(() => {
    fetchGlobalData();
  }, [fetchGlobalData]);

  useEffect(() => {
    fetchInvoices();
  }, [fetchInvoices]);

  // 4. Run LangGraph Autonomous Agent Investigation
  const handleRunInvestigation = async () => {
    if (!selectedInvoiceId) return;
    setIsInvestigating(true);
    try {
      const res = await fetch(`/api/invoices/${selectedInvoiceId}/investigate`, {
        method: 'POST',
      });
      if (res.ok) {
        const report = await res.json();
        setAgentReport(report);
        showToast(`Investigation finished. Recommendation: ${report.recommended_action}`);
      } else {
        showToast('Investigation encountered an error', 'error');
      }
    } catch (err) {
      console.error('Agent investigation error:', err);
      showToast('Agent investigation failed', 'error');
    } finally {
      setIsInvestigating(false);
    }
  };

  // 5. Submit Human-in-the-Loop Decision
  const handleConfirmDecision = async (decisionData) => {
    if (!selectedInvoiceId) return;
    setIsSubmittingDecision(true);
    try {
      const res = await fetch(`/api/invoices/${selectedInvoiceId}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(decisionData),
      });

      if (res.ok) {
        const resData = await res.json();
        showToast(`Invoice updated to ${resData.new_status}. Audit logged.`);
        setDecisionModalOpen(false);

        // Refresh stats and queue
        fetchGlobalData();
        fetchInvoices();

        // Refresh active invoice detail
        const detailRes = await fetch(`/api/invoices/${selectedInvoiceId}`);
        if (detailRes.ok) {
          setInvoiceDetail(await detailRes.json());
        }
      } else {
        showToast('Failed to record decision', 'error');
      }
    } catch (err) {
      console.error('Error submitting decision:', err);
      showToast('Error recording decision', 'error');
    } finally {
      setIsSubmittingDecision(false);
    }
  };

  // 6. Export Power BI Data Marts
  const handleExportMarts = async () => {
    setIsExporting(true);
    try {
      const res = await fetch('/api/marts/export');
      if (res.ok) {
        showToast('Power BI Data Marts generated (CSV & Parquet)');
      } else {
        showToast('Failed to export data marts', 'error');
      }
    } catch (err) {
      console.error('Export error:', err);
      showToast('Error exporting data marts', 'error');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="app-container">
      {/* Toast Notification */}
      {toastMessage && (
        <div style={{
          position: 'fixed',
          top: '74px',
          right: '24px',
          zIndex: 1000,
          padding: '10px 16px',
          borderRadius: '8px',
          background: toastMessage.type === 'error' ? 'rgba(244, 63, 94, 0.95)' : 'rgba(16, 185, 129, 0.95)',
          color: '#FFFFFF',
          fontSize: '0.82rem',
          fontWeight: '700',
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)',
          backdropFilter: 'blur(8px)'
        }}>
          {toastMessage.text}
        </div>
      )}

      {/* Top Header */}
      <Header
        stats={stats}
        onExportMarts={handleExportMarts}
        isExporting={isExporting}
        apiHealthy={apiHealthy}
      />

      {/* Main Split Layout */}
      <div className="main-content">
        {/* Left Queue Sidebar */}
        <InvoiceQueue
          invoices={invoices}
          selectedInvoiceId={selectedInvoiceId}
          onSelectInvoice={(id) => setSelectedInvoiceId(id)}
          searchTerm={searchTerm}
          onSearchChange={(term) => { setSearchTerm(term); setPage(1); }}
          statusFilter={statusFilter}
          onStatusFilterChange={(st) => { setStatusFilter(st); setPage(1); }}
          currencyFilter={currencyFilter}
          onCurrencyFilterChange={(cur) => { setCurrencyFilter(cur); setPage(1); }}
          page={page}
          totalPages={totalPages}
          onPageChange={(p) => setPage(p)}
          isLoading={isLoadingQueue}
        />

        {/* Central Workspace Area */}
        <div className="workspace-area">
          {/* Split Panes: PDF Viewer vs Reconciliation Matrix */}
          <div className="split-panes">
            <PdfViewerPane invoiceDetail={invoiceDetail} />
            <ReconciliationMatrixPane invoiceDetail={invoiceDetail} />
          </div>

          {/* Bottom LangGraph Autonomous Agent Station */}
          <AgentDrawer
            invoiceNumber={selectedInvoiceId}
            agentReport={agentReport}
            isInvestigating={isInvestigating}
            onRunInvestigation={handleRunInvestigation}
            onOpenDecisionModal={(decision) => {
              setTargetDecision(decision);
              setDecisionModalOpen(true);
            }}
          />
        </div>
      </div>

      {/* Decision Override Modal */}
      <DecisionModal
        isOpen={decisionModalOpen}
        onClose={() => setDecisionModalOpen(false)}
        invoiceNumber={selectedInvoiceId}
        targetDecision={targetDecision}
        defaultReason={agentReport ? agentReport.case_summary : 'Standard reconciliation action'}
        onConfirmDecision={handleConfirmDecision}
        isSubmitting={isSubmittingDecision}
      />
    </div>
  );
}

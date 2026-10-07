import React from 'react';
import { Search, Filter, AlertTriangle, CheckCircle, Clock, ShieldAlert, FileText, ChevronLeft, ChevronRight } from 'lucide-react';

export default function InvoiceQueue({
  invoices,
  selectedInvoiceId,
  onSelectInvoice,
  searchTerm,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  currencyFilter,
  onCurrencyFilterChange,
  page,
  totalPages,
  onPageChange,
  isLoading
}) {
  return (
    <aside className="queue-sidebar">
      {/* Search & Filter Controls */}
      <div style={{ padding: '16px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <Search size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '12px' }} />
          <input
            type="text"
            placeholder="Search invoice, vendor, or PO..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 12px 8px 36px',
              background: 'rgba(15, 23, 42, 0.7)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              color: 'var(--text-primary)',
              fontSize: '0.85rem',
              outline: 'none',
              fontFamily: 'var(--font-sans)'
            }}
          />
        </div>

        {/* Filter Pills */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {['ALL', 'APPROVED', 'ON_HOLD', 'ESCALATED', 'PENDING'].map((s) => (
            <button
              key={s}
              onClick={() => onStatusFilterChange(s)}
              style={{
                fontSize: '0.7rem',
                fontWeight: '600',
                padding: '3px 8px',
                borderRadius: '6px',
                cursor: 'pointer',
                border: '1px solid',
                borderColor: statusFilter === s ? 'var(--accent-agent)' : 'var(--border-subtle)',
                background: statusFilter === s ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
                color: statusFilter === s ? '#A5B4FC' : 'var(--text-secondary)',
                transition: 'all 0.15s ease'
              }}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Currency Selector */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: '700' }}>
            Currency:
          </span>
          <div style={{ display: 'flex', gap: '4px' }}>
            {['ALL', 'EUR', 'USD', 'INR'].map((curr) => (
              <button
                key={curr}
                onClick={() => onCurrencyFilterChange(curr)}
                style={{
                  fontSize: '0.68rem',
                  fontWeight: '600',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  border: 'none',
                  background: currencyFilter === curr ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.04)',
                  color: currencyFilter === curr ? '#FFFFFF' : 'var(--text-muted)'
                }}
              >
                {curr}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Invoice List Items */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
        {isLoading ? (
          <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Loading reconciliation queue...
          </div>
        ) : invoices.length === 0 ? (
          <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            No invoices match current filters.
          </div>
        ) : (
          invoices.map((inv) => {
            const isSelected = selectedInvoiceId === inv.invoice_number;
            const hasDiscrepancy = inv.has_discrepancy;

            let badgeClass = 'badge-pending';
            let dotColor = 'dot-amber';
            if (inv.match_status === 'APPROVED') {
              badgeClass = 'badge-approved';
              dotColor = 'dot-green';
            } else if (inv.match_status === 'ON_HOLD') {
              badgeClass = 'badge-hold';
              dotColor = 'dot-amber';
            } else if (inv.match_status === 'ESCALATED') {
              badgeClass = 'badge-escalated';
              dotColor = 'dot-red';
            }

            return (
              <div
                key={inv.invoice_number}
                onClick={() => onSelectInvoice(inv.invoice_number)}
                className="stitch-card"
                style={{
                  padding: '12px 14px',
                  marginBottom: '8px',
                  cursor: 'pointer',
                  background: isSelected ? 'rgba(30, 41, 59, 0.95)' : 'rgba(15, 23, 42, 0.6)',
                  borderColor: isSelected ? 'var(--accent-agent)' : 'var(--border-subtle)',
                  boxShadow: isSelected ? '0 0 12px rgba(99, 102, 241, 0.25)' : 'none',
                  position: 'relative',
                  overflow: 'hidden'
                }}
              >
                {isSelected && (
                  <div style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    bottom: 0,
                    width: '3px',
                    background: 'var(--accent-agent)'
                  }} />
                )}

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span className="font-mono" style={{ fontSize: '0.85rem', fontWeight: '700', color: '#F8FAFC' }}>
                    {inv.invoice_number}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {inv.is_scanned && (
                      <span style={{
                        fontSize: '0.65rem',
                        fontWeight: '700',
                        color: '#38BDF8',
                        background: 'rgba(56, 189, 248, 0.15)',
                        padding: '1px 5px',
                        borderRadius: '4px'
                      }}>
                        OCR
                      </span>
                    )}
                    <span className={`badge ${badgeClass}`} style={{ fontSize: '0.65rem', padding: '2px 6px' }}>
                      <span className={`status-dot ${dotColor}`} />
                      {inv.match_status}
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                  <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '210px' }}>
                    {inv.vendor_name}
                  </span>
                  <span className="font-mono" style={{ fontWeight: '600', color: '#F1F5F9' }}>
                    {inv.currency} {inv.total_gross_amount?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '6px', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  <span>PO: {inv.po_number || 'NONE'}</span>
                  <span>{inv.invoice_date}</span>
                </div>

                {hasDiscrepancy && inv.defect_types && inv.defect_types.length > 0 && (
                  <div style={{ marginTop: '8px', display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                    {inv.defect_types.map((dt) => (
                      <span
                        key={dt}
                        style={{
                          fontSize: '0.64rem',
                          fontWeight: '600',
                          padding: '2px 5px',
                          borderRadius: '3px',
                          background: 'rgba(244, 63, 94, 0.15)',
                          color: '#FB7185',
                          border: '1px solid rgba(244, 63, 94, 0.3)'
                        }}
                      >
                        {dt.replace(/_/g, ' ')}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Pagination Footer */}
      <div style={{
        padding: '10px 16px',
        borderTop: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '0.75rem',
        color: 'var(--text-muted)'
      }}>
        <span>Page {page} of {Math.max(totalPages, 1)}</span>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            className="btn-stitch btn-stitch-ghost"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            style={{ padding: '4px 8px', fontSize: '0.75rem' }}
          >
            <ChevronLeft size={14} />
          </button>
          <button
            className="btn-stitch btn-stitch-ghost"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            style={{ padding: '4px 8px', fontSize: '0.75rem' }}
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </aside>
  );
}

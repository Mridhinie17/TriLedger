import React, { useState } from 'react';
import { Search, Filter, AlertTriangle, CheckCircle, Clock, ShieldAlert, FileText, ChevronLeft, ChevronRight, Hash, Sparkles } from 'lucide-react';

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
      {/* Top Search & Filter Bar */}
      <div style={{
        padding: '16px',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        background: 'rgba(10, 14, 26, 0.4)'
      }}>
        {/* Search Input with Keyboard Badge */}
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <Search size={15} color="#64748B" style={{ position: 'absolute', left: '12px' }} />
          <input
            type="text"
            placeholder="Search invoice, vendor, or PO..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            style={{
              width: '100%',
              padding: '9px 40px 9px 36px',
              background: 'rgba(15, 23, 42, 0.6)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '10px',
              color: 'var(--text-primary)',
              fontSize: '0.82rem',
              outline: 'none',
              fontFamily: 'var(--font-sans)',
              transition: 'border-color 0.2s ease, box-shadow 0.2s ease'
            }}
            onFocus={(e) => {
              e.target.style.borderColor = 'rgba(99, 102, 241, 0.6)';
              e.target.style.boxShadow = '0 0 16px rgba(99, 102, 241, 0.25)';
            }}
            onBlur={(e) => {
              e.target.style.borderColor = 'rgba(255, 255, 255, 0.1)';
              e.target.style.boxShadow = 'none';
            }}
          />
          <span className="kbd-hint" style={{ position: 'absolute', right: '10px' }}>
            /
          </span>
        </div>

        {/* Filter Pills with Aesthetic Neon Accents */}
        <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
          {[
            { id: 'ALL', label: 'All' },
            { id: 'APPROVED', label: 'Approved' },
            { id: 'ON_HOLD', label: 'On Hold' },
            { id: 'ESCALATED', label: 'Escalated' },
            { id: 'PENDING', label: 'Pending' }
          ].map(({ id, label }) => {
            const isActive = statusFilter === id;
            return (
              <button
                key={id}
                onClick={() => onStatusFilterChange(id)}
                style={{
                  fontSize: '0.7rem',
                  fontWeight: '700',
                  padding: '4px 9px',
                  borderRadius: '7px',
                  cursor: 'pointer',
                  border: '1px solid',
                  borderColor: isActive ? 'rgba(99, 102, 241, 0.5)' : 'rgba(255, 255, 255, 0.08)',
                  background: isActive ? 'linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(139, 92, 246, 0.25))' : 'rgba(255, 255, 255, 0.03)',
                  color: isActive ? '#C7D2FE' : '#94A3B8',
                  boxShadow: isActive ? '0 0 12px rgba(99, 102, 241, 0.25)' : 'none',
                  transition: 'all 0.15s ease'
                }}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* Currency Switcher */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '2px' }}>
          <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: '800', letterSpacing: '0.04em' }}>
            Currency
          </span>
          <div style={{ display: 'flex', gap: '4px', background: 'rgba(255, 255, 255, 0.04)', padding: '2px', borderRadius: '6px' }}>
            {['ALL', 'INR', 'EUR', 'USD'].map((curr) => {
              const isCurrActive = currencyFilter === curr;
              return (
                <button
                  key={curr}
                  onClick={() => onCurrencyFilterChange(curr)}
                  style={{
                    fontSize: '0.66rem',
                    fontWeight: '700',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    border: 'none',
                    background: isCurrActive ? 'rgba(255, 255, 255, 0.16)' : 'transparent',
                    color: isCurrActive ? '#FFFFFF' : '#64748B',
                    boxShadow: isCurrActive ? '0 1px 4px rgba(0,0,0,0.3)' : 'none',
                    transition: 'all 0.15s ease'
                  }}
                >
                  {curr}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Invoice List Items */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {isLoading ? (
          <div style={{ padding: '40px 16px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem' }}>
            <div className="spin-icon" style={{ display: 'inline-block', marginBottom: '8px' }}>⚡</div>
            <p>Syncing SAP ERP queue...</p>
          </div>
        ) : invoices.length === 0 ? (
          <div style={{ padding: '40px 16px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem' }}>
            No invoices match current filters.
          </div>
        ) : (
          invoices.map((inv) => {
            const isSelected = selectedInvoiceId === inv.invoice_number;
            const hasDiscrepancy = inv.has_discrepancy;

            let badgeClass = 'badge-pending';
            let dotColor = 'dot-amber';
            let statusLabel = 'PENDING';
            if (inv.match_status === 'APPROVED') {
              badgeClass = 'badge-approved';
              dotColor = 'dot-green';
              statusLabel = 'APPROVED';
            } else if (inv.match_status === 'ON_HOLD') {
              badgeClass = 'badge-hold';
              dotColor = 'dot-amber';
              statusLabel = 'HOLD';
            } else if (inv.match_status === 'ESCALATED') {
              badgeClass = 'badge-escalated';
              dotColor = 'dot-red';
              statusLabel = 'ESCALATED';
            }

            return (
              <div
                key={inv.invoice_number}
                onClick={() => onSelectInvoice(inv.invoice_number)}
                style={{
                  padding: '12px 14px',
                  borderRadius: '12px',
                  cursor: 'pointer',
                  border: isSelected
                    ? '1px solid rgba(129, 140, 248, 0.55)'
                    : '1px solid rgba(255, 255, 255, 0.05)',
                  background: isSelected
                    ? 'linear-gradient(135deg, rgba(99, 102, 241, 0.16) 0%, rgba(139, 92, 246, 0.1) 100%)'
                    : 'rgba(15, 23, 42, 0.45)',
                  boxShadow: isSelected
                    ? '0 4px 20px -2px rgba(99, 102, 241, 0.3), inset 0 1px 1px 0 rgba(255, 255, 255, 0.15)'
                    : 'none',
                  transition: 'all 0.18s cubic-bezier(0.16, 1, 0.3, 1)',
                  position: 'relative',
                  overflow: 'hidden'
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)';
                    e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.12)';
                    e.currentTarget.style.transform = 'translateY(-1px)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background = 'rgba(15, 23, 42, 0.45)';
                    e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.05)';
                    e.currentTarget.style.transform = 'translateY(0)';
                  }
                }}
              >
                {/* Active selection bar indicator on left */}
                {isSelected && (
                  <div style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    bottom: 0,
                    width: '3.5px',
                    background: 'linear-gradient(to bottom, #6366F1, #06B6D4)',
                    boxShadow: '0 0 8px #6366F1'
                  }} />
                )}

                {/* Top Row: Invoice ID and Status Badge */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span className="font-mono" style={{
                      fontSize: '0.82rem',
                      fontWeight: '800',
                      color: isSelected ? '#FFFFFF' : '#E2E8F0'
                    }}>
                      {inv.invoice_number}
                    </span>
                    {inv.is_scanned && (
                      <span style={{
                        fontSize: '0.6rem',
                        fontWeight: '700',
                        color: 'var(--accent-cyan)',
                        background: 'rgba(6, 182, 212, 0.12)',
                        padding: '1px 5px',
                        borderRadius: '4px',
                        border: '1px solid rgba(6, 182, 212, 0.25)'
                      }}>
                        OCR
                      </span>
                    )}
                  </div>

                  <span className={`badge ${badgeClass}`} style={{ fontSize: '0.62rem', padding: '2px 7px' }}>
                    <div className={`status-dot ${dotColor}`} style={{ width: '5px', height: '5px' }} />
                    {statusLabel}
                  </span>
                </div>

                {/* Middle Row: Vendor Name */}
                <div style={{
                  fontSize: '0.78rem',
                  fontWeight: '600',
                  color: isSelected ? '#F1F5F9' : '#94A3B8',
                  marginBottom: '6px',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis'
                }}>
                  {inv.vendor_name}
                </div>

                {/* Bottom Row: Amount & Defect / Anomaly Badges */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span className="font-mono" style={{
                      fontSize: '0.84rem',
                      fontWeight: '800',
                      color: isSelected ? '#38BDF8' : '#F8FAFC'
                    }}>
                      {inv.currency} {inv.total_gross_amount?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>

                  <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {inv.invoice_date}
                  </span>
                </div>

                {/* Detected defect pills */}
                {inv.defect_types && inv.defect_types.length > 0 && (
                  <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '6px' }}>
                    {inv.defect_types.slice(0, 2).map((def) => (
                      <span
                        key={def}
                        style={{
                          fontSize: '0.6rem',
                          fontWeight: '700',
                          color: '#FDA4AF',
                          background: 'rgba(244, 63, 94, 0.12)',
                          padding: '1px 6px',
                          borderRadius: '4px',
                          border: '1px solid rgba(244, 63, 94, 0.25)'
                        }}
                      >
                        {def.replace(/_/g, ' ')}
                      </span>
                    ))}
                    {inv.defect_types.length > 2 && (
                      <span style={{
                        fontSize: '0.6rem',
                        fontWeight: '700',
                        color: 'var(--text-muted)',
                        padding: '1px 4px'
                      }}>
                        +{inv.defect_types.length - 2}
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Pagination Footer Bar */}
      <div style={{
        padding: '12px 16px',
        borderTop: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'rgba(10, 14, 26, 0.6)'
      }}>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          Page <strong style={{ color: '#F8FAFC' }}>{page}</strong> of <strong style={{ color: '#F8FAFC' }}>{totalPages}</strong>
        </span>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            style={{
              padding: '4px 8px',
              borderRadius: '6px',
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid var(--border-subtle)',
              color: page <= 1 ? '#475569' : '#CBD5E1',
              cursor: page <= 1 ? 'not-allowed' : 'pointer'
            }}
          >
            <ChevronLeft size={14} />
          </button>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            style={{
              padding: '4px 8px',
              borderRadius: '6px',
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid var(--border-subtle)',
              color: page >= totalPages ? '#475569' : '#CBD5E1',
              cursor: page >= totalPages ? 'not-allowed' : 'pointer'
            }}
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </aside>
  );
}

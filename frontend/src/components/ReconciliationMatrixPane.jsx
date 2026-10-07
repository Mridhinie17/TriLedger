import React from 'react';
import { CheckCircle2, AlertCircle, ShieldAlert, DollarSign, Building2, Truck, FileCheck, ArrowRight, Lock } from 'lucide-react';

export default function ReconciliationMatrixPane({ invoiceDetail }) {
  if (!invoiceDetail) {
    return (
      <div className="stitch-card" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '32px' }}>
        <p style={{ color: 'var(--text-muted)' }}>Select an invoice to inspect reconciliation matrix.</p>
      </div>
    );
  }

  const matchRes = invoiceDetail.match_result || {};
  const isMatched = matchRes.is_matched;
  const discrepancies = matchRes.discrepancies || [];
  const fxVal = matchRes.fx_validation;
  const poDetails = invoiceDetail.po_details;
  const grDetails = invoiceDetail.gr_details;

  return (
    <div className="stitch-card" style={{ height: '100%', display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
      {/* Reconciliation Header Banner */}
      <div style={{
        padding: '16px',
        borderBottom: '1px solid var(--border-subtle)',
        background: isMatched ? 'rgba(16, 185, 129, 0.08)' : 'rgba(244, 63, 94, 0.08)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {isMatched ? (
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              background: 'rgba(16, 185, 129, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#10B981',
              boxShadow: '0 0 12px rgba(16, 185, 129, 0.3)'
            }}>
              <CheckCircle2 size={22} />
            </div>
          ) : (
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              background: 'rgba(244, 63, 94, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#F43F5E',
              boxShadow: '0 0 12px rgba(244, 63, 94, 0.3)'
            }}>
              <AlertCircle size={22} />
            </div>
          )}
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: '800', color: isMatched ? '#10B981' : '#FB7185' }}>
              {isMatched ? '3-Way Reconciliation Passed' : 'Reconciliation Discrepancies Detected'}
            </h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              {isMatched
                ? 'All line items, quantities, pricing, tax, and FX within tolerance limits.'
                : `${discrepancies.length} tolerance breach(es) require auditor action.`}
            </p>
          </div>
        </div>

        {matchRes.isolation_forest_anomaly && (
          <div className="badge badge-escalated" style={{ fontSize: '0.72rem' }}>
            <ShieldAlert size={13} />
            Anomaly Score: {matchRes.isolation_forest_score?.toFixed(3)}
          </div>
        )}
      </div>

      <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Vendor & Entity Cross-Check Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          {/* Vendor Details */}
          <div className="stitch-card-elevated" style={{ padding: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
              <Building2 size={14} color="var(--accent-cyan)" />
              <span style={{ fontWeight: '700', textTransform: 'uppercase' }}>Vendor Entity Check</span>
            </div>
            <div style={{ fontSize: '0.82rem', fontWeight: '700', color: '#F8FAFC' }}>
              {invoiceDetail.vendor_name}
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              ID: <span className="font-mono">{invoiceDetail.vendor_id}</span> | Tax ID: {invoiceDetail.vendor_tax_id || 'N/A'}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '6px', fontSize: '0.72rem', color: '#34D399' }}>
              <Lock size={12} />
              <span>Bank Account: <strong className="font-mono">{invoiceDetail.vendor_bank_masked}</strong></span>
            </div>
          </div>

          {/* PO & GR Alignment */}
          <div className="stitch-card-elevated" style={{ padding: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
              <FileCheck size={14} color="var(--accent-agent)" />
              <span style={{ fontWeight: '700', textTransform: 'uppercase' }}>ERP Document Chain</span>
            </div>
            {poDetails ? (
              <>
                <div style={{ fontSize: '0.82rem', fontWeight: '700', color: '#F8FAFC' }}>
                  PO: <span className="font-mono">{poDetails.po_number}</span>
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  PO Total: <strong className="font-mono">{poDetails.currency} {poDetails.total_gross_amount?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong>
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Goods Receipts: <strong>{grDetails?.count || 0} receipt records matched</strong>
                </div>
              </>
            ) : (
              <div style={{ color: '#F43F5E', fontSize: '0.78rem', fontWeight: '600' }}>
                ❌ No matching PO found in SAP ERP (Phantom / Missing PO)
              </div>
            )}
          </div>
        </div>

        {/* Foreign Exchange Official ECB Validation */}
        {invoiceDetail.currency !== 'EUR' && (
          <div className="stitch-card-elevated" style={{ padding: '12px', borderLeft: '3px solid var(--accent-cyan)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.75rem', fontWeight: '700', color: 'var(--accent-cyan)' }}>
                <DollarSign size={15} />
                <span>OFFICIAL ECB REFERENCE FX RATE VALIDATION</span>
              </div>
              <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>ECB Triangular Parity</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', fontSize: '0.78rem' }}>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>Claimed Rate:</span>
                <p className="font-mono" style={{ fontWeight: '700', color: '#F8FAFC' }}>
                  {invoiceDetail.stated_fx_rate?.toFixed(4)}
                </p>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>Official ECB Rate:</span>
                <p className="font-mono" style={{ fontWeight: '700', color: '#38BDF8' }}>
                  {fxVal ? fxVal.official_rate?.toFixed(4) : invoiceDetail.stated_fx_rate?.toFixed(4)}
                </p>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>Variance / Status:</span>
                <p className="font-mono" style={{
                  fontWeight: '700',
                  color: fxVal && !fxVal.is_valid ? '#F43F5E' : '#10B981'
                }}>
                  {fxVal ? `${fxVal.percentage_variance?.toFixed(2)}%` : '0.00%'} ({fxVal && !fxVal.is_valid ? 'BREACH' : 'OK'})
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Discrepancy Diagnostics Alerts */}
        {discrepancies.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <h4 style={{ fontSize: '0.78rem', color: '#FB7185', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: '700' }}>
              Tolerance Breach Diagnostics ({discrepancies.length})
            </h4>
            {discrepancies.map((d, i) => (
              <div
                key={i}
                style={{
                  padding: '10px 12px',
                  borderRadius: '8px',
                  background: 'rgba(244, 63, 94, 0.1)',
                  border: '1px solid rgba(244, 63, 94, 0.25)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '8px'
                }}
              >
                <AlertCircle size={16} color="#FB7185" style={{ flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: '800', color: '#FB7185' }}>
                      {d.check_type}
                    </span>
                    <span className="badge" style={{ fontSize: '0.6rem', padding: '1px 5px', background: 'rgba(244, 63, 94, 0.2)', color: '#FDA4AF' }}>
                      {d.severity} SEVERITY
                    </span>
                  </div>
                  <p style={{ fontSize: '0.74rem', color: '#F1F5F9', marginTop: '2px' }}>
                    {d.message}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 3-Way Line Item Comparison Table */}
        <div>
          <h4 style={{ fontSize: '0.8rem', color: '#94A3B8', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: '700' }}>
            3-Way Line Item Matching Matrix
          </h4>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.74rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', textAlign: 'left', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '8px' }}>Line</th>
                  <th style={{ padding: '8px' }}>Description</th>
                  <th style={{ padding: '8px' }}>PO Ordered</th>
                  <th style={{ padding: '8px' }}>GR Received</th>
                  <th style={{ padding: '8px' }}>Invoice Billed</th>
                  <th style={{ padding: '8px', textAlign: 'right' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {invoiceDetail.items?.map((it, idx) => {
                  const poItem = poDetails?.items?.[idx];
                  const qtyMismatch = poItem && Math.abs(poItem.quantity - it.quantity) > 0.001;
                  const priceMismatch = poItem && Math.abs(poItem.unit_price - it.unit_price) > 0.50;

                  return (
                    <tr
                      key={it.line_number}
                      style={{
                        borderBottom: '1px solid rgba(255,255,255,0.04)',
                        background: (qtyMismatch || priceMismatch) ? 'rgba(244, 63, 94, 0.05)' : 'transparent'
                      }}
                    >
                      <td className="font-mono" style={{ padding: '8px', color: 'var(--text-muted)' }}>
                        {it.line_number}
                      </td>
                      <td style={{ padding: '8px', color: '#F8FAFC', maxWidth: '160px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {it.item_description}
                      </td>
                      <td className="font-mono" style={{ padding: '8px', color: 'var(--text-secondary)' }}>
                        {poItem ? `${poItem.quantity} @ ${poItem.unit_price?.toFixed(2)}` : 'N/A'}
                      </td>
                      <td className="font-mono" style={{ padding: '8px', color: 'var(--text-secondary)' }}>
                        {grDetails?.receipts?.[idx] ? `${grDetails.receipts[idx].quantity_received}` : 'N/A'}
                      </td>
                      <td className="font-mono" style={{
                        padding: '8px',
                        color: (qtyMismatch || priceMismatch) ? '#FB7185' : '#F1F5F9',
                        fontWeight: (qtyMismatch || priceMismatch) ? '700' : 'normal'
                      }}>
                        {it.quantity} @ {it.unit_price?.toFixed(2)}
                      </td>
                      <td style={{ padding: '8px', textAlign: 'right' }}>
                        {(qtyMismatch || priceMismatch) ? (
                          <span className="badge badge-escalated" style={{ fontSize: '0.62rem', padding: '1px 5px' }}>
                            Variance
                          </span>
                        ) : (
                          <span className="badge badge-approved" style={{ fontSize: '0.62rem', padding: '1px 5px' }}>
                            Matched
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

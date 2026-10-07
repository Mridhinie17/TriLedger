import React, { useState } from 'react';
import { CheckCircle2, AlertCircle, ShieldAlert, DollarSign, Building2, Truck, FileCheck, ArrowRight, Lock, Copy, Check } from 'lucide-react';

export default function ReconciliationMatrixPane({ invoiceDetail }) {
  const [copiedBank, setCopiedBank] = useState(false);

  if (!invoiceDetail) {
    return (
      <div className="stitch-card" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '32px' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Select an invoice from the queue to inspect reconciliation.</p>
      </div>
    );
  }

  const matchRes = invoiceDetail.match_result || {};
  const isMatched = matchRes.is_matched;
  const discrepancies = matchRes.discrepancies || [];
  const fxVal = matchRes.fx_validation;
  const poDetails = invoiceDetail.po_details;
  const grDetails = invoiceDetail.gr_details;

  const copyBank = (account) => {
    if (account) {
      navigator.clipboard.writeText(account);
      setCopiedBank(true);
      setTimeout(() => setCopiedBank(false), 2000);
    }
  };

  return (
    <div className="stitch-card" style={{ height: '100%', display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
      {/* Top Status Banner */}
      <div style={{
        padding: '14px 18px',
        borderBottom: '1px solid var(--border-subtle)',
        background: isMatched ? 'rgba(16, 185, 129, 0.06)' : 'rgba(244, 63, 94, 0.06)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {isMatched ? (
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              background: 'rgba(16, 185, 129, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#34D399'
            }}>
              <CheckCircle2 size={18} />
            </div>
          ) : (
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              background: 'rgba(244, 63, 94, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#FB7185'
            }}>
              <AlertCircle size={18} />
            </div>
          )}
          <div>
            <h3 style={{
              fontSize: '0.95rem',
              fontWeight: '700',
              color: isMatched ? '#34D399' : '#FB7185'
            }}>
              {isMatched ? '3-Way Match Passed' : 'Reconciliation Discrepancy'}
            </h3>
            <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
              {isMatched
                ? 'PO price, Goods Receipt quantity, and FX rates matched within tolerance.'
                : `${discrepancies.length} discrepancy item(s) require review.`}
            </p>
          </div>
        </div>

        {matchRes.isolation_forest_anomaly && (
          <div className="badge badge-escalated" style={{ fontSize: '0.7rem' }}>
            <ShieldAlert size={12} />
            Anomaly Score: {matchRes.isolation_forest_score?.toFixed(3)}
          </div>
        )}
      </div>

      {/* Main Inspection Body */}
      <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
        
        {/* Row 1: Vendor Details & Document References */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          
          {/* Vendor Details */}
          <div className="stitch-card-elevated" style={{ padding: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px', color: 'var(--accent-cyan)', fontSize: '0.72rem', fontWeight: '700' }}>
              <Building2 size={13} />
              <span>Vendor Details</span>
            </div>
            
            <div style={{ fontSize: '0.84rem', fontWeight: '700', color: '#F8FAFC', marginBottom: '4px' }}>
              {invoiceDetail.vendor_name}
            </div>
            
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'flex', gap: '8px', marginBottom: '8px' }}>
              <span>ID: <strong className="font-mono" style={{ color: '#E2E8F0' }}>{invoiceDetail.vendor_id}</strong></span>
              <span>•</span>
              <span>Tax ID: <strong className="font-mono" style={{ color: '#E2E8F0' }}>{invoiceDetail.vendor_tax_id || 'N/A'}</strong></span>
            </div>

            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '5px 8px',
              borderRadius: '6px',
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid var(--border-subtle)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: '#34D399' }}>
                <Lock size={11} />
                <span>Bank: <strong className="font-mono">{invoiceDetail.vendor_bank_masked}</strong></span>
              </div>
              <button
                onClick={() => copyBank(invoiceDetail.vendor_bank_masked)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: copiedBank ? '#34D399' : 'var(--text-muted)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  fontSize: '0.68rem'
                }}
                title="Copy account"
              >
                {copiedBank ? <Check size={12} /> : <Copy size={12} />}
              </button>
            </div>
          </div>

          {/* PO & Receipts Card */}
          <div className="stitch-card-elevated" style={{ padding: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px', color: 'var(--accent-indigo)', fontSize: '0.72rem', fontWeight: '700' }}>
              <FileCheck size={13} />
              <span>Purchase Order & Receipts</span>
            </div>

            {poDetails ? (
              <>
                <div style={{ fontSize: '0.84rem', fontWeight: '700', color: '#F8FAFC', marginBottom: '4px' }}>
                  PO: <span className="font-mono" style={{ color: '#818CF8' }}>{poDetails.po_number}</span>
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                  PO Total: <strong className="font-mono" style={{ color: '#F8FAFC' }}>{poDetails.currency} {poDetails.total_gross_amount?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong>
                </div>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '0.72rem',
                  padding: '5px 8px',
                  borderRadius: '6px',
                  background: 'rgba(99, 102, 241, 0.06)',
                  border: '1px solid rgba(99, 102, 241, 0.15)',
                  color: '#C7D2FE'
                }}>
                  <Truck size={12} />
                  <span>Goods Receipts: <strong>{grDetails?.count || 0} record(s) matched</strong></span>
                </div>
              </>
            ) : (
              <div style={{
                color: '#FB7185',
                fontSize: '0.75rem',
                fontWeight: '600',
                padding: '8px',
                borderRadius: '6px',
                background: 'rgba(244, 63, 94, 0.08)',
                border: '1px solid rgba(244, 63, 94, 0.2)'
              }}>
                Missing PO reference in ERP system
              </div>
            )}
          </div>
        </div>

        {/* Foreign Exchange Rate Validation */}
        {invoiceDetail.currency !== 'EUR' && (
          <div className="stitch-card-elevated" style={{ padding: '12px', borderLeft: '3px solid var(--accent-cyan)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.74rem', fontWeight: '700', color: 'var(--accent-cyan)' }}>
                <DollarSign size={13} />
                <span>Exchange Rate Validation</span>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
              <div style={{ padding: '6px 10px', borderRadius: '6px', background: 'rgba(255, 255, 255, 0.02)' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.68rem' }}>Claimed Rate</span>
                <p className="font-mono" style={{ fontWeight: '700', fontSize: '0.86rem', color: '#F8FAFC', marginTop: '2px' }}>
                  {invoiceDetail.stated_fx_rate?.toFixed(4)}
                </p>
              </div>

              <div style={{ padding: '6px 10px', borderRadius: '6px', background: 'rgba(255, 255, 255, 0.02)' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.68rem' }}>ECB Reference Rate</span>
                <p className="font-mono" style={{ fontWeight: '700', fontSize: '0.86rem', color: '#38BDF8', marginTop: '2px' }}>
                  {fxVal ? fxVal.official_rate?.toFixed(4) : invoiceDetail.stated_fx_rate?.toFixed(4)}
                </p>
              </div>

              <div style={{ padding: '6px 10px', borderRadius: '6px', background: 'rgba(255, 255, 255, 0.02)' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.68rem' }}>Rate Variance</span>
                <p className="font-mono" style={{
                  fontWeight: '700',
                  fontSize: '0.86rem',
                  marginTop: '2px',
                  color: fxVal && !fxVal.is_valid ? '#FB7185' : '#34D399'
                }}>
                  {fxVal ? `${fxVal.deviation_pct?.toFixed(2)}%` : '0.00%'} ({fxVal && !fxVal.is_valid ? 'BREACH' : 'OK'})
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Discrepancies Alerts */}
        {discrepancies.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <h4 style={{ fontSize: '0.72rem', color: '#FB7185', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
              Exceptions ({discrepancies.length})
            </h4>

            {discrepancies.map((d, idx) => (
              <div
                key={idx}
                style={{
                  padding: '8px 12px',
                  borderRadius: '8px',
                  background: 'rgba(244, 63, 94, 0.08)',
                  border: '1px solid rgba(244, 63, 94, 0.25)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="badge badge-escalated" style={{ fontSize: '0.62rem', padding: '1px 5px' }}>
                    {d.check_type}
                  </span>
                  <span style={{ fontSize: '0.76rem', color: '#F1F5F9' }}>
                    {d.message}
                  </span>
                </div>
                <span style={{ fontSize: '0.68rem', color: '#FDA4AF', fontWeight: '600' }}>
                  {d.severity}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* 3-Way Line Item Matching Table */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <h4 style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
            Line Item Comparison
          </h4>

          <div style={{
            borderRadius: '8px',
            border: '1px solid var(--border-subtle)',
            overflow: 'hidden',
            background: 'rgba(15, 23, 42, 0.3)'
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.76rem' }}>
              <thead>
                <tr style={{ background: 'rgba(255, 255, 255, 0.03)', borderBottom: '1px solid var(--border-subtle)', textAlign: 'left' }}>
                  <th style={{ padding: '8px 10px', color: 'var(--text-muted)' }}>Line</th>
                  <th style={{ padding: '8px 10px', color: 'var(--text-muted)' }}>Description</th>
                  <th style={{ padding: '8px 10px', color: 'var(--text-muted)', textAlign: 'center' }}>PO Qty</th>
                  <th style={{ padding: '8px 10px', color: 'var(--text-muted)', textAlign: 'center' }}>GR Qty</th>
                  <th style={{ padding: '8px 10px', color: 'var(--text-muted)', textAlign: 'center' }}>Inv Qty</th>
                  <th style={{ padding: '8px 10px', color: 'var(--text-muted)', textAlign: 'right' }}>PO Price</th>
                  <th style={{ padding: '8px 10px', color: 'var(--text-muted)', textAlign: 'right' }}>Inv Price</th>
                  <th style={{ padding: '8px 10px', color: 'var(--text-muted)', textAlign: 'center' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {invoiceDetail.items?.map((item) => {
                  const poItem = poDetails?.items?.find((p) => p.line_number === item.line_number);
                  const grItem = grDetails?.receipts?.find((g) => g.line_number === item.line_number);

                  const qtyMatches = grItem ? grItem.quantity_received === item.quantity : false;
                  const priceMatches = poItem ? Math.abs(poItem.unit_price - item.unit_price) <= (poItem.unit_price * 0.01) : false;
                  const lineOk = qtyMatches && priceMatches;

                  return (
                    <tr
                      key={item.line_number}
                      style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.03)' }}
                    >
                      <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                        #{item.line_number}
                      </td>
                      <td style={{ padding: '8px 10px', color: '#F8FAFC' }}>
                        {item.item_description}
                      </td>
                      <td style={{ padding: '8px 10px', textAlign: 'center', fontFamily: 'var(--font-mono)' }}>
                        {poItem ? poItem.quantity : '-'}
                      </td>
                      <td style={{ padding: '8px 10px', textAlign: 'center', fontFamily: 'var(--font-mono)' }}>
                        {grItem ? grItem.quantity_received : '-'}
                      </td>
                      <td style={{ padding: '8px 10px', textAlign: 'center', fontFamily: 'var(--font-mono)', fontWeight: '700', color: qtyMatches ? '#34D399' : '#FB7185' }}>
                        {item.quantity}
                      </td>
                      <td style={{ padding: '8px 10px', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                        {poItem ? poItem.unit_price.toFixed(2) : '-'}
                      </td>
                      <td style={{ padding: '8px 10px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: '700', color: priceMatches ? '#34D399' : '#FB7185' }}>
                        {item.unit_price.toFixed(2)}
                      </td>
                      <td style={{ padding: '8px 10px', textAlign: 'center' }}>
                        {lineOk ? (
                          <span className="badge badge-matched" style={{ fontSize: '0.6rem', padding: '1px 5px' }}>
                            MATCH
                          </span>
                        ) : (
                          <span className="badge badge-escalated" style={{ fontSize: '0.6rem', padding: '1px 5px' }}>
                            VARIANCE
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

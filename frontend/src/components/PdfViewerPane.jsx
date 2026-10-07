import React, { useState } from 'react';
import { FileText, Download, Eye, ExternalLink, ShieldCheck, Cpu, Code2, Hash } from 'lucide-react';

export default function PdfViewerPane({ invoiceDetail }) {
  const [viewMode, setViewMode] = useState('extracted'); // 'extracted' | 'pdf'

  if (!invoiceDetail) {
    return (
      <div className="stitch-card" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '32px' }}>
        <p style={{ color: 'var(--text-muted)' }}>Select an invoice from the queue to view document.</p>
      </div>
    );
  }

  const pdfUrl = `/api/invoices/${invoiceDetail.invoice_number}/pdf`;

  return (
    <div className="stitch-card" style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Pane Top Bar */}
      <div style={{
        padding: '12px 18px',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'rgba(15, 23, 42, 0.5)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '28px',
            height: '28px',
            borderRadius: '8px',
            background: 'rgba(99, 102, 241, 0.15)',
            border: '1px solid rgba(99, 102, 241, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#818CF8'
          }}>
            <FileText size={16} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="font-mono" style={{ fontSize: '0.86rem', fontWeight: '800', color: '#F8FAFC' }}>
                {invoiceDetail.invoice_number}.pdf
              </span>
              <span style={{
                fontSize: '0.66rem',
                fontWeight: '600',
                padding: '2px 6px',
                borderRadius: '4px',
                background: 'rgba(255, 255, 255, 0.05)',
                color: 'var(--text-muted)'
              }}>
                {invoiceDetail.is_scanned ? 'Scanned' : 'Digital'}
              </span>
            </div>
          </div>
        </div>

        {/* View Mode & Download Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            display: 'flex',
            background: 'rgba(255, 255, 255, 0.05)',
            borderRadius: '8px',
            padding: '3px',
            border: '1px solid var(--border-subtle)'
          }}>
            <button
              onClick={() => setViewMode('extracted')}
              style={{
                padding: '4px 10px',
                fontSize: '0.72rem',
                fontWeight: '700',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                background: viewMode === 'extracted' ? 'rgba(99, 102, 241, 0.35)' : 'transparent',
                color: viewMode === 'extracted' ? '#FFFFFF' : 'var(--text-muted)',
                transition: 'all 0.15s ease'
              }}
            >
              Extracted Schema
            </button>
            <button
              onClick={() => setViewMode('pdf')}
              style={{
                padding: '4px 10px',
                fontSize: '0.72rem',
                fontWeight: '700',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                background: viewMode === 'pdf' ? 'rgba(99, 102, 241, 0.35)' : 'transparent',
                color: viewMode === 'pdf' ? '#FFFFFF' : 'var(--text-muted)',
                transition: 'all 0.15s ease'
              }}
            >
              PDF Document
            </button>
          </div>

          <a
            href={pdfUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-stitch btn-stitch-ghost"
            style={{ padding: '5px 8px', borderRadius: '6px' }}
            title="Open PDF in new tab"
          >
            <ExternalLink size={13} />
          </a>
        </div>
      </div>

      {/* Pane Content */}
      <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
        {viewMode === 'pdf' ? (
          <iframe
            src={pdfUrl}
            title={`Invoice PDF ${invoiceDetail.invoice_number}`}
            style={{ width: '100%', height: '100%', border: 'none', background: '#0F172A' }}
          />
        ) : (
          <div style={{ padding: '16px', height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ fontSize: '0.74rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.03em', color: 'var(--text-secondary)' }}>
                Line Items
              </div>
            </div>

            <div style={{
              borderRadius: '10px',
              border: '1px solid var(--border-subtle)',
              overflow: 'hidden',
              background: 'rgba(15, 23, 42, 0.4)'
            }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
                <thead>
                  <tr style={{ background: 'rgba(255, 255, 255, 0.04)', borderBottom: '1px solid var(--border-subtle)', textAlign: 'left' }}>
                    <th style={{ padding: '8px 12px', color: 'var(--text-muted)' }}>Line</th>
                    <th style={{ padding: '8px 12px', color: 'var(--text-muted)' }}>Description</th>
                    <th style={{ padding: '8px 12px', color: 'var(--text-muted)', textAlign: 'center' }}>Qty</th>
                    <th style={{ padding: '8px 12px', color: 'var(--text-muted)', textAlign: 'right' }}>Price</th>
                    <th style={{ padding: '8px 12px', color: 'var(--text-muted)', textAlign: 'center' }}>Tax %</th>
                    <th style={{ padding: '8px 12px', color: 'var(--text-muted)', textAlign: 'right' }}>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {invoiceDetail.items?.map((item) => (
                    <tr
                      key={item.line_number}
                      style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}
                    >
                      <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                        #{item.line_number}
                      </td>
                      <td style={{ padding: '8px 12px', color: '#F1F5F9', fontWeight: '500' }}>
                        {item.item_description}
                      </td>
                      <td style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'var(--font-mono)' }}>
                        {item.quantity} {item.unit_of_measure}
                      </td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                        {invoiceDetail.currency} {item.unit_price.toFixed(2)}
                      </td>
                      <td style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                        {item.tax_rate_pct}%
                      </td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: '700', color: '#38BDF8' }}>
                        {invoiceDetail.currency} {item.total_amount.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Subtotal & Tax Breakdown */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
              padding: '12px 16px',
              borderRadius: '10px',
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid var(--border-subtle)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
                <span>Subtotal Net:</span>
                <span className="font-mono">{invoiceDetail.currency} {invoiceDetail.total_net_amount?.toFixed(2)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
                <span>Tax Amount:</span>
                <span className="font-mono">{invoiceDetail.currency} {invoiceDetail.total_tax_amount?.toFixed(2)}</span>
              </div>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: '0.88rem',
                fontWeight: '800',
                color: '#F8FAFC',
                borderTop: '1px solid rgba(255, 255, 255, 0.08)',
                paddingTop: '6px',
                marginTop: '2px'
              }}>
                <span>Gross Payable:</span>
                <span className="font-mono" style={{ color: '#38BDF8' }}>
                  {invoiceDetail.currency} {invoiceDetail.total_gross_amount?.toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

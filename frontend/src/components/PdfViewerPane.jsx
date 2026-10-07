import React, { useState } from 'react';
import { FileText, Download, Eye, ExternalLink, ShieldCheck, Cpu } from 'lucide-react';

export default function PdfViewerPane({ invoiceDetail }) {
  const [viewMode, setViewMode] = useState('pdf'); // 'pdf' | 'extracted'

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
        padding: '12px 16px',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'rgba(15, 23, 42, 0.7)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <FileText size={18} color="var(--accent-agent)" />
          <div>
            <span className="font-mono" style={{ fontSize: '0.88rem', fontWeight: '700', color: '#F8FAFC' }}>
              {invoiceDetail.invoice_number}.pdf
            </span>
            <span style={{ marginLeft: '8px', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              {invoiceDetail.is_scanned ? 'Scanned Raster (OCR Processed)' : 'Digital Native PDF'}
            </span>
          </div>
        </div>

        {/* View Mode & Download Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ display: 'flex', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', padding: '2px' }}>
            <button
              onClick={() => setViewMode('pdf')}
              style={{
                padding: '4px 8px',
                fontSize: '0.72rem',
                fontWeight: '600',
                borderRadius: '4px',
                border: 'none',
                cursor: 'pointer',
                background: viewMode === 'pdf' ? 'rgba(99, 102, 241, 0.3)' : 'transparent',
                color: viewMode === 'pdf' ? '#A5B4FC' : 'var(--text-muted)'
              }}
            >
              PDF Document
            </button>
            <button
              onClick={() => setViewMode('extracted')}
              style={{
                padding: '4px 8px',
                fontSize: '0.72rem',
                fontWeight: '600',
                borderRadius: '4px',
                border: 'none',
                cursor: 'pointer',
                background: viewMode === 'extracted' ? 'rgba(99, 102, 241, 0.3)' : 'transparent',
                color: viewMode === 'extracted' ? '#A5B4FC' : 'var(--text-muted)'
              }}
            >
              OCR Raw Data
            </button>
          </div>

          <a
            href={pdfUrl}
            target="_blank"
            rel="noreferrer"
            className="btn-stitch btn-stitch-ghost"
            style={{ padding: '4px 8px', fontSize: '0.75rem' }}
            title="Open in new window"
          >
            <ExternalLink size={14} />
          </a>
        </div>
      </div>

      {/* Pane Content */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {viewMode === 'pdf' ? (
          <iframe
            src={pdfUrl}
            title={`Invoice ${invoiceDetail.invoice_number}`}
            style={{
              width: '100%',
              height: '100%',
              border: 'none',
              background: '#0F172A'
            }}
          />
        ) : (
          <div style={{ padding: '16px', height: '100%', overflowY: 'auto', background: 'rgba(11, 16, 28, 0.95)' }}>
            <h4 style={{ fontSize: '0.82rem', color: '#94A3B8', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Extracted Line Item Schema
            </h4>

            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', textAlign: 'left', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '8px' }}>Line</th>
                  <th style={{ padding: '8px' }}>Description</th>
                  <th style={{ padding: '8px' }}>Qty</th>
                  <th style={{ padding: '8px' }}>Price</th>
                  <th style={{ padding: '8px' }}>Tax %</th>
                  <th style={{ padding: '8px', textAlign: 'right' }}>Total</th>
                </tr>
              </thead>
              <tbody>
                {invoiceDetail.items?.map((it) => (
                  <tr key={it.line_number} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    <td className="font-mono" style={{ padding: '8px', color: 'var(--text-muted)' }}>{it.line_number}</td>
                    <td style={{ padding: '8px', color: '#F1F5F9' }}>{it.item_description}</td>
                    <td className="font-mono" style={{ padding: '8px' }}>{it.quantity} {it.unit_of_measure}</td>
                    <td className="font-mono" style={{ padding: '8px' }}>{invoiceDetail.currency} {it.unit_price?.toFixed(2)}</td>
                    <td className="font-mono" style={{ padding: '8px' }}>{it.tax_rate_pct}%</td>
                    <td className="font-mono" style={{ padding: '8px', textAlign: 'right', fontWeight: '600', color: '#38BDF8' }}>
                      {invoiceDetail.currency} {it.total_amount?.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div style={{ marginTop: '20px', padding: '12px', background: 'rgba(255,255,255,0.03)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Subtotal Net:</span>
                <span className="font-mono">{invoiceDetail.currency} {invoiceDetail.total_net_amount?.toFixed(2)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Tax Amount:</span>
                <span className="font-mono">{invoiceDetail.currency} {invoiceDetail.total_tax_amount?.toFixed(2)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', fontWeight: '700', color: '#F8FAFC', borderTop: '1px solid var(--border-subtle)', paddingTop: '6px', marginTop: '6px' }}>
                <span>Gross Payable:</span>
                <span className="font-mono" style={{ color: 'var(--accent-cyan)' }}>{invoiceDetail.currency} {invoiceDetail.total_gross_amount?.toFixed(2)}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

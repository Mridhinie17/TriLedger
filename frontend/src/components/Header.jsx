import React from 'react';
import { ShieldCheck, BarChart3, Database, RefreshCw, Layers, Cpu } from 'lucide-react';

export default function Header({ stats, onExportMarts, isExporting, apiHealthy }) {
  return (
    <header className="header-bar">
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '34px',
            height: '34px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #6366F1 0%, #06B6D4 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 16px rgba(99, 102, 241, 0.4)'
          }}>
            <Layers size={20} color="#FFFFFF" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.1rem', fontWeight: '800', letterSpacing: '-0.02em', color: '#F8FAFC' }}>
                TriLedger
              </span>
              <span style={{
                fontSize: '0.65rem',
                fontWeight: '700',
                background: 'rgba(99, 102, 241, 0.2)',
                color: '#A5B4FC',
                padding: '2px 6px',
                borderRadius: '4px',
                border: '1px solid rgba(99, 102, 241, 0.4)'
              }}>
                STITCH v1.0
              </span>
            </div>
            <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', lineHeight: '1' }}>
              Autonomous 3-Way AP Reconciliation & ECB FX Engine
            </p>
          </div>
        </div>
      </div>

      {/* KPI Chips */}
      {stats && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div className="stitch-card" style={{ padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>STP Rate:</span>
            <span className="font-mono" style={{
              fontSize: '0.85rem',
              fontWeight: '700',
              color: stats.straight_through_processing_pct >= 80 ? '#10B981' : '#F59E0B'
            }}>
              {stats.straight_through_processing_pct}%
            </span>
          </div>

          <div className="stitch-card" style={{ padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Exceptions:</span>
            <span className="font-mono" style={{ fontSize: '0.85rem', fontWeight: '700', color: '#F43F5E' }}>
              {stats.exception_count}
            </span>
          </div>

          <div className="stitch-card" style={{ padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Total Spend:</span>
            <span className="font-mono" style={{ fontSize: '0.85rem', fontWeight: '700', color: '#F8FAFC' }}>
              €{stats.total_spend_eur?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </span>
          </div>

          <div className="stitch-card" style={{ padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Anomalies:</span>
            <span className="font-mono" style={{ fontSize: '0.85rem', fontWeight: '700', color: '#FBBF24' }}>
              {stats.high_risk_anomalies}
            </span>
          </div>
        </div>
      )}

      {/* Action Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <button
          className="btn-stitch btn-stitch-ghost"
          onClick={onExportMarts}
          disabled={isExporting}
          style={{ fontSize: '0.8rem', padding: '6px 12px' }}
          title="Export Spend, Exception, Aging, Open Payables and FX marts to Parquet and CSV"
        >
          <Database size={15} className={isExporting ? 'spin-icon' : ''} />
          {isExporting ? 'Exporting...' : 'Export Power BI Marts'}
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 10px', borderRadius: '6px', background: 'rgba(255,255,255,0.03)' }}>
          <div className={`status-dot ${apiHealthy ? 'dot-green' : 'dot-red'}`} />
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            {apiHealthy ? 'API Connected' : 'Connecting...'}
          </span>
        </div>
      </div>
    </header>
  );
}

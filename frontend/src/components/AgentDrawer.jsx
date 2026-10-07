import React from 'react';
import { Bot, Sparkles, ShieldCheck, ShieldAlert, CheckCircle, Clock, AlertTriangle, ArrowRight, CornerDownRight } from 'lucide-react';

export default function AgentDrawer({
  invoiceNumber,
  agentReport,
  isInvestigating,
  onRunInvestigation,
  onOpenDecisionModal
}) {
  const steps = [
    { id: 'sanitize_and_scan', label: '1. Sanitize & Scan Injection' },
    { id: 'gather_evidence', label: '2. Gather ERP Evidence' },
    { id: 'reason_and_analyze', label: '3. Reason & Analyze' },
    { id: 'enforce_guardrails', label: '4. Enforce Guardrails' },
    { id: 'log_audit_trail', label: '5. Log Audit Trail' },
  ];

  return (
    <div className="stitch-card-elevated" style={{
      borderTop: '1px solid var(--border-subtle)',
      background: 'rgba(11, 16, 28, 0.95)',
      padding: '16px 20px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px'
    }}>
      {/* Drawer Header & Trigger */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 12px rgba(99, 102, 241, 0.4)'
          }}>
            <Bot size={18} color="#FFFFFF" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.92rem', fontWeight: '800', color: '#F8FAFC' }}>
                LangGraph Autonomous Reconciliation Agent
              </span>
              <span className="badge badge-agent" style={{ fontSize: '0.64rem' }}>
                Active Agent
              </span>
            </div>
            <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Self-directed investigation with read-only ERP tools and immutable audit logging
            </p>
          </div>
        </div>

        {/* Action Buttons & Runner */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            className="btn-stitch btn-stitch-primary"
            onClick={onRunInvestigation}
            disabled={isInvestigating}
            style={{ fontSize: '0.8rem', padding: '6px 14px' }}
          >
            <Sparkles size={14} className={isInvestigating ? 'spin-icon' : ''} />
            {isInvestigating ? 'Investigating...' : 'Run Agent Investigation'}
          </button>

          {/* Decision Actions */}
          <div style={{ display: 'flex', gap: '6px', borderLeft: '1px solid var(--border-subtle)', paddingLeft: '10px' }}>
            <button
              className="btn-stitch btn-stitch-success"
              onClick={() => onOpenDecisionModal('APPROVE')}
              style={{ fontSize: '0.75rem', padding: '6px 10px' }}
            >
              Approve
            </button>
            <button
              className="btn-stitch btn-stitch-warning"
              onClick={() => onOpenDecisionModal('ON_HOLD')}
              style={{ fontSize: '0.75rem', padding: '6px 10px' }}
            >
              Hold
            </button>
            <button
              className="btn-stitch btn-stitch-danger"
              onClick={() => onOpenDecisionModal('ESCALATE')}
              style={{ fontSize: '0.75rem', padding: '6px 10px' }}
            >
              Escalate
            </button>
          </div>
        </div>
      </div>

      {/* StateGraph Workflow Timeline */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '8px 14px',
        background: 'rgba(15, 23, 42, 0.6)',
        borderRadius: '8px',
        border: '1px solid var(--border-subtle)'
      }}>
        {steps.map((st, idx) => (
          <React.Fragment key={st.id}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem' }}>
              <div style={{
                width: '16px',
                height: '16px',
                borderRadius: '50%',
                background: agentReport ? '#10B981' : (isInvestigating ? 'var(--accent-agent)' : 'rgba(255,255,255,0.1)'),
                color: '#FFFFFF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.6rem',
                fontWeight: '700'
              }}>
                ✓
              </div>
              <span style={{ color: agentReport ? '#E2E8F0' : 'var(--text-muted)', fontWeight: agentReport ? '600' : 'normal' }}>
                {st.label}
              </span>
            </div>
            {idx < steps.length - 1 && (
              <ArrowRight size={12} color="var(--border-highlight)" />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Investigation Results */}
      {agentReport ? (
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1.2fr 2fr',
          gap: '14px',
          background: 'rgba(15, 23, 42, 0.4)',
          borderRadius: '8px',
          padding: '12px',
          border: '1px solid var(--border-subtle)'
        }}>
          {/* Left: Decision & Confidence */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', borderRight: '1px solid var(--border-subtle)', paddingRight: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: '700' }}>
                Recommended Action
              </span>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                Confidence: <strong className="font-mono" style={{ color: '#F8FAFC' }}>{(agentReport.confidence * 100).toFixed(1)}%</strong>
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className={`badge ${agentReport.recommended_action === 'APPROVE' ? 'badge-approved' : (agentReport.recommended_action === 'HOLD' ? 'badge-hold' : 'badge-escalated')}`} style={{ fontSize: '0.85rem', padding: '4px 12px' }}>
                {agentReport.recommended_action}
              </span>

              {agentReport.is_adversarial_injection_detected && (
                <span className="badge badge-escalated" style={{ fontSize: '0.7rem' }}>
                  <ShieldAlert size={12} />
                  Injection Blocked
                </span>
              )}
            </div>

            {/* Cited ERP Records */}
            <div style={{ marginTop: '4px' }}>
              <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: '700' }}>
                Cited Ground Truth Records:
              </span>
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '4px' }}>
                {agentReport.cited_records?.map((rec) => (
                  <span
                    key={rec}
                    className="font-mono"
                    style={{
                      fontSize: '0.68rem',
                      padding: '2px 6px',
                      background: 'rgba(99, 102, 241, 0.15)',
                      color: '#A5B4FC',
                      borderRadius: '4px',
                      border: '1px solid rgba(99, 102, 241, 0.3)'
                    }}
                  >
                    {rec}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Right: Case Summary & Explanation */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: '700', color: '#F8FAFC' }}>
              {agentReport.case_summary}
            </div>
            <p style={{ fontSize: '0.73rem', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
              {agentReport.discrepancy_explanation}
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px', fontSize: '0.68rem', color: '#10B981' }}>
              <ShieldCheck size={12} />
              <span>Immutable SAP AuditLog write verified ({invoiceNumber})</span>
            </div>
          </div>
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '12px', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
          Click "Run Agent Investigation" to trigger autonomous reconciliation reasoning.
        </div>
      )}
    </div>
  );
}

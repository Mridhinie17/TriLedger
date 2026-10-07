import React, { useState } from 'react';
import { ShieldCheck, X } from 'lucide-react';

export default function DecisionModal({
  isOpen,
  onClose,
  invoiceNumber,
  targetDecision,
  defaultReason,
  onConfirmDecision,
  isSubmitting
}) {
  if (!isOpen) return null;

  const [analystName, setAnalystName] = useState('senior_auditor@enterprise.com');
  const [reason, setReason] = useState(defaultReason || 'Automated reconciliation policy approval');
  const [notes, setNotes] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    onConfirmDecision({
      decision: targetDecision,
      analyst_name: analystName,
      reason: reason,
      notes: notes
    });
  };

  let titleColor = '#10B981';
  if (targetDecision === 'ON_HOLD') titleColor = '#F59E0B';
  if (targetDecision === 'ESCALATE') titleColor = '#F43F5E';

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 100
    }}>
      <div className="stitch-card-elevated" style={{
        width: '480px',
        maxWidth: '90vw',
        padding: '24px',
        border: '1px solid var(--border-highlight)',
        boxShadow: '0 20px 40px rgba(0, 0, 0, 0.5)'
      }}>
        {/* Modal Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldCheck size={20} color={titleColor} />
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#F8FAFC' }}>
              Confirm Decision: <span style={{ color: titleColor }}>{targetDecision}</span>
            </h3>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          >
            <X size={18} />
          </button>
        </div>

        <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '16px' }}>
          Document: <strong className="font-mono" style={{ color: '#F8FAFC' }}>{invoiceNumber}</strong>. This action writes directly to the immutable SAP ERP AuditLog table.
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div>
            <label style={{ fontSize: '0.74rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
              Analyst Identifier
            </label>
            <input
              type="text"
              value={analystName}
              onChange={(e) => setAnalystName(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '8px 12px',
                background: 'rgba(15, 23, 42, 0.8)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '6px',
                color: '#F8FAFC',
                fontSize: '0.82rem',
                outline: 'none'
              }}
            />
          </div>

          <div>
            <label style={{ fontSize: '0.74rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
              Justification / Business Reason
            </label>
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '8px 12px',
                background: 'rgba(15, 23, 42, 0.8)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '6px',
                color: '#F8FAFC',
                fontSize: '0.82rem',
                outline: 'none',
                fontFamily: 'var(--font-sans)',
                resize: 'none'
              }}
            />
          </div>

          <div>
            <label style={{ fontSize: '0.74rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
              Internal Notes (Optional)
            </label>
            <input
              type="text"
              placeholder="e.g. Cross-checked with warehouse manager"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                background: 'rgba(15, 23, 42, 0.8)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '6px',
                color: '#F8FAFC',
                fontSize: '0.82rem',
                outline: 'none'
              }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button
              type="button"
              className="btn-stitch btn-stitch-ghost"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-stitch btn-stitch-primary"
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Recording Action...' : 'Record Immutable Action'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

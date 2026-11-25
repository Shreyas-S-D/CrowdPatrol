import React from 'react';
import { Shield, LayoutDashboard } from 'lucide-react';

export default function Footer({ onLaunchDashboard }) {
  return (
    <footer className="footer-wrapper">
      <div className="container">
        {/* Pre-footer Call to Action Banner */}
        <div className="cta-banner glass-card">
          <h2 className="cta-heading">Ready to Experience Autonomous Crowd Monitoring?</h2>
          <p className="cta-sub">
            Navigate to the live monitoring dashboard to inspect multi-camera video streams, 
            spatial density heatmaps, and automated emergency notification dispatchers.
          </p>
          <button onClick={onLaunchDashboard} className="btn-primary cta-btn">
            <LayoutDashboard size={20} />
            <span>Launch Monitoring Dashboard</span>
          </button>
        </div>

        {/* Footer Top */}
        <div className="footer-top">
          <div className="footer-brand">
            <div className="footer-brand-title">
              <Shield size={24} className="footer-shield" />
              <span>Crowd<span className="brand-accent">Patrol</span></span>
            </div>
            <p className="footer-brand-desc">
              Autonomous AI Crowd Monitoring & Emergency Risk Mitigation Platform
            </p>
          </div>

          <div className="footer-links">
            <a href="#hero" className="footer-link">Home</a>
            <a href="#overview" className="footer-link">Overview</a>
            <a href="#capabilities" className="footer-link">Capabilities</a>
            <a href="#how-it-works" className="footer-link">Architecture</a>
            <a href="#tech-stack" className="footer-link">Technology</a>
            <a href="#applications" className="footer-link">Applications</a>
          </div>
        </div>

        {/* Footer Bottom */}
        <div className="footer-bottom">
          <div className="footer-credits">
            <strong>AMC Engineering College</strong> — Department of Computer Science & Engineering<br />
            Final Year Major Project Demonstration (Phase 7 Standalone Web Application)
          </div>
          <div className="footer-disclaimer">
            Academic Prototype Notice: Developed for experimental crowd density & safety research benchmarking.
          </div>
        </div>
      </div>

      <style>{`
        .footer-wrapper {
          padding: 48px 0 32px 0;
          border-top: 1px solid var(--border-color);
          margin-top: 64px;
        }
        .cta-banner {
          padding: 48px 32px;
          text-align: center;
          background: linear-gradient(135deg, rgba(29, 78, 216, 0.28) 0%, rgba(14, 165, 233, 0.15) 100%);
          border: 1px solid rgba(56, 189, 248, 0.35);
          margin-bottom: 56px;
        }
        .cta-heading {
          font-size: 2.2rem;
          font-weight: 800;
          color: #FFFFFF;
          margin-bottom: 14px;
        }
        .cta-sub {
          max-width: 680px;
          margin: 0 auto 28px auto;
          font-size: 1.08rem;
          color: var(--text-secondary);
          line-height: 1.6;
        }
        .cta-btn {
          padding: 14px 32px;
          font-size: 1.05rem;
        }
        .footer-top {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 24px;
          padding-bottom: 32px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .footer-brand-title {
          display: flex;
          align-items: center;
          gap: 10px;
          font-size: 1.4rem;
          font-weight: 800;
          color: #FFFFFF;
          margin-bottom: 6px;
        }
        .footer-shield {
          color: var(--accent-cyan);
        }
        .footer-brand-desc {
          font-size: 0.88rem;
          color: var(--text-muted);
        }
        .footer-links {
          display: flex;
          gap: 22px;
          flex-wrap: wrap;
        }
        .footer-link {
          color: var(--text-secondary);
          text-decoration: none;
          font-size: 0.92rem;
          transition: color 0.2s ease;
        }
        .footer-link:hover {
          color: var(--accent-blue);
        }
        .footer-bottom {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 16px;
          padding-top: 24px;
          font-size: 0.82rem;
          color: var(--text-muted);
        }
        .footer-credits strong {
          color: var(--text-secondary);
        }
        .footer-disclaimer {
          text-align: right;
        }
        @media (max-width: 768px) {
          .cta-heading {
            font-size: 1.7rem;
          }
          .footer-top {
            flex-direction: column;
            align-items: flex-start;
          }
          .footer-bottom {
            flex-direction: column;
            align-items: flex-start;
          }
          .footer-disclaimer {
            text-align: left;
          }
        }
      `}</style>
    </footer>
  );
}

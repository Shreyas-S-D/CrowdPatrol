import React from 'react';
import { LayoutDashboard, ArrowDownCircle, Zap, Users, AlertTriangle, Video } from 'lucide-react';

export default function Hero({ onLaunchDashboard }) {
  return (
    <section id="hero" className="hero-section">
      <div className="container">
        {/* Status Pill */}
        <div className="hero-top-badge">
          <div className="status-pill">
            <span className="pulse-dot"></span>
            <span>Autonomous AI Crowd Safety & Risk Intelligence Platform</span>
          </div>
        </div>

        {/* Main Hero Header */}
        <h1 className="hero-title">
          Smarter Crowd Monitoring.<br />
          <span className="cyan-gradient-text">Safer Public Spaces.</span>
        </h1>

        {/* Subtitle / Value Proposition */}
        <p className="hero-description">
          <strong>CrowdPatrol</strong> is an advanced, autonomous AI-powered crowd monitoring and risk assessment platform. 
          Engineered to prevent stampedes and hazardous overcrowding, CrowdPatrol combines real-time deep neural detection, 
          persistent multi-object tracking, spatial density mapping, and predictive motion dynamics to protect lives in high-density public environments.
        </p>

        {/* CTA Button Group */}
        <div className="hero-cta-group">
          <button onClick={onLaunchDashboard} className="btn-primary hero-btn">
            <LayoutDashboard size={20} />
            <span>Launch Monitoring Dashboard</span>
          </button>
          <a href="#capabilities" className="btn-secondary hero-btn">
            <ArrowDownCircle size={20} />
            <span>Explore Capabilities</span>
          </a>
        </div>

        {/* Hero Performance Telemetry Strip */}
        <div className="hero-stats-strip glass-card">
          <div className="stat-card">
            <div className="stat-icon-wrapper">
              <Zap size={22} className="stat-icon cyan" />
            </div>
            <div className="stat-value">Up to 30 FPS</div>
            <div className="stat-label">Benchmark Target</div>
          </div>

          <div className="stat-card">
            <div className="stat-icon-wrapper">
              <Users size={22} className="stat-icon blue" />
            </div>
            <div className="stat-value">Dual Mode</div>
            <div className="stat-label">Person & Head Tracking</div>
          </div>

          <div className="stat-card">
            <div className="stat-icon-wrapper">
              <AlertTriangle size={22} className="stat-icon amber" />
            </div>
            <div className="stat-value">Automated</div>
            <div className="stat-label">Rapid Alert Dispatch</div>
          </div>

          <div className="stat-card">
            <div className="stat-icon-wrapper">
              <Video size={22} className="stat-icon green" />
            </div>
            <div className="stat-value">Multi-Cam</div>
            <div className="stat-label">CCTV & RTSP Network Grid</div>
          </div>
        </div>
      </div>

      <style>{`
        .hero-section {
          padding: 64px 0 48px 0;
          text-align: center;
        }
        .hero-top-badge {
          margin-bottom: 24px;
        }
        .hero-title {
          font-size: 3.4rem;
          font-weight: 800;
          line-height: 1.15;
          letter-spacing: -0.03em;
          margin-bottom: 24px;
        }
        .hero-description {
          max-width: 820px;
          margin: 0 auto 36px auto;
          font-size: 1.18rem;
          line-height: 1.7;
          color: var(--text-secondary);
        }
        .hero-description strong {
          color: var(--text-primary);
          font-weight: 600;
        }
        .hero-cta-group {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 18px;
          flex-wrap: wrap;
          margin-bottom: 56px;
        }
        .hero-btn {
          min-width: 210px;
        }
        .hero-stats-strip {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 20px;
          padding: 24px 32px;
          margin: 0 auto;
          max-width: 1040px;
        }
        .stat-card {
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
        }
        .stat-icon-wrapper {
          width: 44px;
          height: 44px;
          border-radius: 12px;
          background: rgba(30, 58, 138, 0.3);
          border: 1px solid rgba(56, 189, 248, 0.25);
          display: flex;
          align-items: center;
          justify-content: center;
          margin-bottom: 12px;
        }
        .stat-icon.cyan { color: var(--accent-cyan); }
        .stat-icon.blue { color: var(--accent-blue); }
        .stat-icon.amber { color: var(--accent-amber); }
        .stat-icon.green { color: var(--accent-green); }

        .stat-value {
          font-family: var(--font-mono);
          font-size: 1.65rem;
          font-weight: 700;
          color: #FFFFFF;
          margin-bottom: 4px;
        }
        .stat-label {
          font-size: 0.8rem;
          font-weight: 600;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        @media (max-width: 960px) {
          .hero-title {
            font-size: 2.6rem;
          }
          .hero-description {
            font-size: 1.05rem;
          }
          .hero-stats-strip {
            grid-template-columns: repeat(2, 1fr);
          }
        }
        @media (max-width: 600px) {
          .hero-title {
            font-size: 2.1rem;
          }
          .hero-stats-strip {
            grid-template-columns: 1fr;
          }
          .hero-cta-group {
            flex-direction: column;
            width: 100%;
          }
          .hero-btn {
            width: 100%;
          }
        }
      `}</style>
    </section>
  );
}

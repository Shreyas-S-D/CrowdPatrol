import React from 'react';
import { ArrowLeft, Video, Activity, Users, Flame, AlertTriangle, ShieldCheck, Play, Square, Settings } from 'lucide-react';

export default function DashboardPreview({ onReturnHome }) {
  return (
    <div className="dashboard-preview-page">
      <div className="container">
        {/* Top Bar Navigation */}
        <div className="preview-top-bar glass-card">
          <div className="preview-nav-left">
            <button onClick={onReturnHome} className="btn-secondary return-btn">
              <ArrowLeft size={18} />
              <span>Return to Landing Page</span>
            </button>
            <div className="divider-vertical"></div>
            <div className="preview-title-group">
              <span className="live-indicator">
                <span className="pulse-dot"></span>
                <span>MONITORING COMMAND CENTER</span>
              </span>
              <h2 className="preview-main-title">CrowdPatrol Live Surveillance Hub</h2>
            </div>
          </div>

          <div className="preview-nav-right">
            <div className="mode-badge">
              <ShieldCheck size={16} />
              <span>PERSON MODE (DEFAULT)</span>
            </div>
            <div className="phase-pill">Phase 7 Web Client</div>
          </div>
        </div>

        {/* Notice Banner */}
        <div className="preview-notice-banner glass-card">
          <Activity size={20} className="notice-icon" />
          <div className="notice-text">
            <strong>Monitoring Dashboard Preview (Phase 7):</strong> Full UI layout established. Camera streaming and FastAPI API integration will be activated in the subsequent step per migration protocol.
          </div>
        </div>

        {/* Dashboard Grid Layout Preview */}
        <div className="dashboard-main-grid">
          {/* Left Column: Video Feed & 2x2 CCTV Grid Area */}
          <div className="grid-left-col">
            <div className="glass-card video-card">
              <div className="card-header">
                <div className="header-title">
                  <Video size={18} className="header-icon" />
                  <span>Synchronized Multi-Camera Grid (4-Channel CCTV)</span>
                </div>
                <div className="feed-controls">
                  <span className="feed-tag">2×2 CCTV Grid</span>
                  <span className="feed-tag active">Focus Feed: CAM-01</span>
                </div>
              </div>

              {/* Video Mock Canvas */}
              <div className="video-viewport">
                <div className="video-grid-mock">
                  <div className="cam-box focus-feed">
                    <span className="cam-label">CAM-01 • Main Entrance</span>
                    <div className="cam-center-content">
                      <Video size={36} className="cam-icon" />
                      <span>Camera Feed Ready</span>
                    </div>
                    <div className="cam-meta">Mode: Person • 30 FPS</div>
                  </div>

                  <div className="cam-box">
                    <span className="cam-label">CAM-02 • Overhead Concourse</span>
                    <div className="cam-center-content">
                      <Video size={28} className="cam-icon" />
                      <span>Camera Feed Ready</span>
                    </div>
                    <div className="cam-meta">Mode: Person • 30 FPS</div>
                  </div>

                  <div className="cam-box">
                    <span className="cam-label">CAM-03 • Plaza Corridor</span>
                    <div className="cam-center-content">
                      <Video size={28} className="cam-icon" />
                      <span>Camera Feed Ready</span>
                    </div>
                    <div className="cam-meta">Mode: Person • 30 FPS</div>
                  </div>

                  <div className="cam-box">
                    <span className="cam-label">CAM-04 • Perimeter Gate</span>
                    <div className="cam-center-content">
                      <Video size={28} className="cam-icon" />
                      <span>Camera Feed Ready</span>
                    </div>
                    <div className="cam-meta">Mode: Person • 30 FPS</div>
                  </div>
                </div>
              </div>

              {/* Video Action Footer */}
              <div className="video-footer">
                <div className="action-buttons">
                  <button className="btn-primary start-btn" disabled>
                    <Play size={16} />
                    <span>Start Monitoring</span>
                  </button>
                  <button className="btn-secondary stop-btn" disabled>
                    <Square size={16} />
                    <span>Stop</span>
                  </button>
                </div>
                <div className="stream-diagnostics">
                  <span>Backend: <strong className="green">FastAPI Connected</strong></span>
                  <span>•</span>
                  <span>Target: <strong>YOLOv8 + DeepSORT</strong></span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Telemetry & Risk Metrics Area */}
          <div className="grid-right-col">
            {/* Real-time metrics card */}
            <div className="glass-card telemetry-card">
              <div className="card-header">
                <div className="header-title">
                  <Activity size={18} className="header-icon" />
                  <span>Real-Time Situational Telemetry</span>
                </div>
              </div>

              <div className="metrics-grid">
                <div className="metric-box">
                  <div className="metric-title">Tracked Persons</div>
                  <div className="metric-value">--</div>
                  <div className="metric-sub">Full-body active tracks</div>
                </div>

                <div className="metric-box">
                  <div className="metric-title">Max Cell Density</div>
                  <div className="metric-value">--</div>
                  <div className="metric-sub">Persons per grid unit</div>
                </div>

                <div className="metric-box">
                  <div className="metric-title">Average Velocity</div>
                  <div className="metric-value">-- px/f</div>
                  <div className="metric-sub">Directional Heading</div>
                </div>

                <div className="metric-box">
                  <div className="metric-title">Anomaly Score</div>
                  <div className="metric-value">0.00</div>
                  <div className="metric-sub">Normal movement</div>
                </div>
              </div>

              {/* Composite Hazard Card */}
              <div className="hazard-box">
                <div className="hazard-title">Multi-Factor Risk Assessment</div>
                <div className="hazard-score">NORMAL (LOW)</div>
                <div className="hazard-desc">Composite safety index combining spatial occupancy & motion entropy</div>
              </div>
            </div>

            {/* Alert Status Card */}
            <div className="glass-card alerts-preview-card">
              <div className="card-header">
                <div className="header-title">
                  <AlertTriangle size={18} className="header-icon amber" />
                  <span>Emergency Alert Feeds</span>
                </div>
              </div>
              <div className="alert-empty-state">
                <ShieldCheck size={32} className="alert-safe-icon" />
                <p>System Operating Within Safe Thresholds</p>
                <span>Automated Gmail SMTP alerts active for High/Critical incidents.</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .dashboard-preview-page {
          padding: 24px 0 64px 0;
          min-height: 100vh;
        }
        .preview-top-bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 16px 24px;
          margin-bottom: 20px;
          flex-wrap: wrap;
          gap: 16px;
        }
        .preview-nav-left {
          display: flex;
          align-items: center;
          gap: 20px;
        }
        .return-btn {
          padding: 8px 16px;
          font-size: 0.9rem;
        }
        .divider-vertical {
          width: 1px;
          height: 32px;
          background: rgba(255, 255, 255, 0.15);
        }
        .preview-title-group {
          display: flex;
          flex-direction: column;
        }
        .live-indicator {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 0.72rem;
          font-weight: 700;
          color: var(--accent-cyan);
          letter-spacing: 0.08em;
        }
        .preview-main-title {
          font-size: 1.35rem;
          font-weight: 700;
          color: #FFFFFF;
          margin: 0;
        }
        .preview-nav-right {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .mode-badge {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 6px 12px;
          background: rgba(30, 58, 138, 0.35);
          border: 1px solid rgba(56, 189, 248, 0.3);
          border-radius: 8px;
          font-size: 0.75rem;
          font-weight: 700;
          color: var(--accent-blue);
        }
        .phase-pill {
          padding: 6px 12px;
          background: rgba(16, 185, 129, 0.15);
          border: 1px solid rgba(16, 185, 129, 0.35);
          border-radius: 8px;
          font-size: 0.75rem;
          font-weight: 700;
          color: var(--accent-green);
        }
        .preview-notice-banner {
          display: flex;
          align-items: center;
          gap: 14px;
          padding: 14px 20px;
          background: rgba(14, 165, 233, 0.1);
          border-color: rgba(56, 189, 248, 0.3);
          margin-bottom: 24px;
        }
        .notice-icon {
          color: var(--accent-cyan);
          flex-shrink: 0;
        }
        .notice-text {
          font-size: 0.92rem;
          color: var(--text-primary);
        }
        .dashboard-main-grid {
          display: grid;
          grid-template-columns: 1.6fr 1fr;
          gap: 24px;
        }
        .video-card, .telemetry-card, .alerts-preview-card {
          padding: 20px;
          margin-bottom: 24px;
        }
        .card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 16px;
          flex-wrap: wrap;
          gap: 10px;
        }
        .header-title {
          display: flex;
          align-items: center;
          gap: 10px;
          font-size: 1.05rem;
          font-weight: 700;
          color: #FFFFFF;
        }
        .header-icon {
          color: var(--accent-cyan);
        }
        .header-icon.amber {
          color: var(--accent-amber);
        }
        .feed-controls {
          display: flex;
          gap: 8px;
        }
        .feed-tag {
          font-size: 0.75rem;
          padding: 4px 10px;
          border-radius: 6px;
          background: rgba(255, 255, 255, 0.06);
          color: var(--text-secondary);
        }
        .feed-tag.active {
          background: rgba(0, 210, 255, 0.15);
          border: 1px solid var(--accent-cyan);
          color: var(--accent-cyan);
        }
        .video-viewport {
          background: #04070D;
          border-radius: 12px;
          padding: 12px;
          border: 1px solid rgba(255, 255, 255, 0.08);
          aspect-ratio: 16 / 9;
          display: flex;
        }
        .video-grid-mock {
          width: 100%;
          height: 100%;
          display: grid;
          grid-template-columns: 1fr 1fr;
          grid-template-rows: 1fr 1fr;
          gap: 8px;
        }
        .cam-box {
          background: rgba(13, 22, 45, 0.85);
          border: 1px solid rgba(59, 130, 246, 0.25);
          border-radius: 8px;
          padding: 12px;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          position: relative;
        }
        .cam-box.focus-feed {
          border-color: var(--accent-cyan);
          box-shadow: inset 0 0 12px rgba(0, 210, 255, 0.15);
        }
        .cam-label {
          font-size: 0.72rem;
          font-weight: 700;
          color: #FFFFFF;
          background: rgba(0, 0, 0, 0.6);
          padding: 2px 8px;
          border-radius: 4px;
          width: fit-content;
        }
        .cam-center-content {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 8px;
          color: var(--text-muted);
          font-size: 0.82rem;
        }
        .cam-icon {
          color: var(--accent-blue);
          opacity: 0.6;
        }
        .cam-meta {
          font-size: 0.7rem;
          color: var(--text-muted);
          text-align: right;
        }
        .video-footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-top: 16px;
          flex-wrap: wrap;
          gap: 12px;
        }
        .action-buttons {
          display: flex;
          gap: 12px;
        }
        .start-btn {
          padding: 8px 18px;
          font-size: 0.88rem;
        }
        .stop-btn {
          padding: 8px 18px;
          font-size: 0.88rem;
        }
        .stream-diagnostics {
          display: flex;
          gap: 8px;
          font-size: 0.82rem;
          color: var(--text-secondary);
        }
        .green {
          color: var(--accent-green);
        }
        .metrics-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
          margin-bottom: 16px;
        }
        .metric-box {
          background: rgba(10, 18, 36, 0.6);
          border: 1px solid rgba(59, 130, 246, 0.15);
          border-radius: 10px;
          padding: 14px;
        }
        .metric-title {
          font-size: 0.78rem;
          color: var(--text-muted);
          font-weight: 600;
          text-transform: uppercase;
        }
        .metric-value {
          font-family: var(--font-mono);
          font-size: 1.5rem;
          font-weight: 700;
          color: var(--accent-cyan);
          margin: 4px 0;
        }
        .metric-sub {
          font-size: 0.74rem;
          color: var(--text-muted);
        }
        .hazard-box {
          background: rgba(16, 185, 129, 0.1);
          border: 1px solid rgba(16, 185, 129, 0.3);
          border-radius: 10px;
          padding: 16px;
          text-align: center;
        }
        .hazard-title {
          font-size: 0.78rem;
          font-weight: 700;
          color: var(--accent-green);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .hazard-score {
          font-family: var(--font-mono);
          font-size: 1.6rem;
          font-weight: 800;
          color: var(--accent-green);
          margin: 4px 0;
        }
        .hazard-desc {
          font-size: 0.76rem;
          color: var(--text-secondary);
        }
        .alert-empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          padding: 24px;
        }
        .alert-safe-icon {
          color: var(--accent-green);
          margin-bottom: 10px;
        }
        .alert-empty-state p {
          font-size: 0.95rem;
          font-weight: 600;
          color: #FFFFFF;
          margin-bottom: 4px;
        }
        .alert-empty-state span {
          font-size: 0.8rem;
          color: var(--text-muted);
        }

        @media (max-width: 960px) {
          .dashboard-main-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
}

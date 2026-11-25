import React from 'react';
import { EyeOff, ShieldCheck, Activity, Award } from 'lucide-react';

export default function Overview() {
  return (
    <section id="overview" className="overview-section">
      <div className="container">
        <div className="section-header">
          <div className="section-tag">Project Background</div>
          <h2 className="section-title">The CrowdPatrol Vision</h2>
          <p className="section-desc">
            Transforming municipal and venue video infrastructure from passive incident recording into an active, life-saving automated intelligence layer.
          </p>
        </div>

        <div className="glass-card overview-card">
          <div className="overview-grid">
            <div className="overview-text-block">
              <div className="academic-badge">
                <Award size={18} className="badge-icon" />
                <span>AMC Engineering College — Final Year Major Project</span>
              </div>
              <h3 className="overview-subtitle">
                Preventing Disasters Before They Unfold
              </h3>
              <p className="overview-body">
                Crowd disasters, stampedes, and dangerous bottleneck crushes around the globe have claimed thousands of lives. 
                Traditional CCTV surveillance relies heavily on human operators who experience cognitive fatigue when attempting 
                to visually monitor dozens of simultaneous camera feeds. By the time a human operator notices localized congestion, 
                panic or crowd collapse has often already begun.
              </p>
              <p className="overview-body">
                <strong>CrowdPatrol</strong> solves this critical challenge by integrating cutting-edge computer vision at the edge. 
                Our neural pipeline continuously quantifies localized spatial densities, monitors crowd surge velocity vectors, and computes 
                a standardized composite risk index. The instant hazard thresholds are exceeded, automated alerts notify on-site security 
                teams and emergency responders via automated high-priority alerts.
              </p>
            </div>

            <div className="overview-pillars">
              <div className="pillar-item">
                <div className="pillar-icon-box">
                  <EyeOff size={22} className="pillar-icon" />
                </div>
                <div>
                  <h4 className="pillar-title">Privacy by Design</h4>
                  <p className="pillar-desc">
                    Strictly tracks crowd density metrics, velocity vectors, and spatial physics. Zero individual facial recognition, identity profiling, or invasive biometric harvesting.
                  </p>
                </div>
              </div>

              <div className="pillar-item">
                <div className="pillar-icon-box">
                  <Activity size={22} className="pillar-icon" />
                </div>
                <div>
                  <h4 className="pillar-title">Rapid Situational Awareness</h4>
                  <p className="pillar-desc">
                    Replaces delayed human reaction with automated detection of panic motion, stampede velocity spikes, and spatial choke points in real time.
                  </p>
                </div>
              </div>

              <div className="pillar-item">
                <div className="pillar-icon-box">
                  <ShieldCheck size={22} className="pillar-icon" />
                </div>
                <div>
                  <h4 className="pillar-title">High-Efficiency Commodity Edge</h4>
                  <p className="pillar-desc">
                    Engineered to execute seamlessly on commodity hardware, existing IP CCTV networks, USB cameras, and mobile phone RTSP streams with low power and zero paid APIs.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .overview-section {
          padding: 48px 0;
        }
        .overview-card {
          padding: 40px;
          border: 1px solid var(--border-color);
        }
        .overview-grid {
          display: grid;
          grid-template-columns: 1.2fr 1fr;
          gap: 40px;
          align-items: center;
        }
        .academic-badge {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 6px 14px;
          border-radius: 8px;
          background: rgba(30, 58, 138, 0.3);
          border: 1px solid rgba(56, 189, 248, 0.3);
          color: var(--accent-blue);
          font-size: 0.82rem;
          font-weight: 600;
          margin-bottom: 16px;
        }
        .badge-icon {
          color: var(--accent-cyan);
        }
        .overview-subtitle {
          font-size: 1.85rem;
          font-weight: 700;
          color: #FFFFFF;
          line-height: 1.3;
          margin-bottom: 16px;
        }
        .overview-body {
          font-size: 1.02rem;
          line-height: 1.7;
          color: var(--text-secondary);
          margin-bottom: 16px;
        }
        .overview-body strong {
          color: var(--text-primary);
        }
        .overview-pillars {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }
        .pillar-item {
          display: flex;
          gap: 16px;
          padding: 16px;
          background: rgba(10, 18, 36, 0.5);
          border: 1px solid rgba(59, 130, 246, 0.15);
          border-radius: 12px;
          transition: all 0.25s ease;
        }
        .pillar-item:hover {
          border-color: var(--border-glow);
          background: rgba(15, 26, 52, 0.7);
        }
        .pillar-icon-box {
          width: 42px;
          height: 42px;
          border-radius: 10px;
          background: rgba(30, 58, 138, 0.35);
          border: 1px solid rgba(56, 189, 248, 0.25);
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }
        .pillar-icon {
          color: var(--accent-cyan);
        }
        .pillar-title {
          font-size: 1.05rem;
          font-weight: 600;
          color: #FFFFFF;
          margin-bottom: 4px;
        }
        .pillar-desc {
          font-size: 0.88rem;
          color: var(--text-secondary);
          line-height: 1.5;
        }

        @media (max-width: 960px) {
          .overview-grid {
            grid-template-columns: 1fr;
            gap: 32px;
          }
          .overview-card {
            padding: 28px 20px;
          }
        }
      `}</style>
    </section>
  );
}

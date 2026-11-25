import React from 'react';
import { Camera, Cpu, Move, Grid, Gauge, BellRing } from 'lucide-react';

const steps = [
  {
    num: "1",
    icon: Camera,
    title: "Video Capture",
    desc: "Ingestion of camera streams: built-in webcams, USB cameras, smartphone Wi-Fi (IP/DroidCam), RTSP CCTV grids, or recorded benchmark files."
  },
  {
    num: "2",
    icon: Cpu,
    title: "YOLOv8 Detection",
    desc: "High-speed PyTorch inference generating bounding boxes and confidence scores for persons and overhead heads with optional 2×2 spatial tiling."
  },
  {
    num: "3",
    icon: Move,
    title: "DeepSORT Tracking",
    desc: "Kalman filter kinematics coupled with MobileNetV2 deep appearance embeddings to track and preserve persistent cross-frame identities."
  },
  {
    num: "4",
    icon: Grid,
    title: "Density & Motion",
    desc: "Spatial cell occupancy mapping, crowd influx velocity computation, and optical flow vectors tracking heading directions."
  },
  {
    num: "5",
    icon: Gauge,
    title: "Risk Assessment",
    desc: "Composite mathematical risk engine calculating real-time safety scores, surge rates, and danger thresholds (Low, Medium, High)."
  },
  {
    num: "6",
    icon: BellRing,
    title: "Dashboard & Alerts",
    desc: "Reactive low-latency dashboard visualization, real-time Firebase telemetry cloud sync, and automated Gmail SMTP alert dispatches."
  }
];

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="how-it-works-section">
      <div className="container">
        <div className="section-header">
          <div className="section-tag">Pipeline Architecture</div>
          <h2 className="section-title">How CrowdPatrol Operates</h2>
          <p className="section-desc">
            A modular, zero-latency computer vision pipeline designed for continuous 24/7 autonomous surveillance.
          </p>
        </div>

        <div className="pipeline-container">
          {steps.map((step, idx) => {
            const IconComp = step.icon;
            return (
              <div key={idx} className="glass-card pipeline-step-card">
                <div className="step-badge">{step.num}</div>
                <div className="step-icon-box">
                  <IconComp size={24} className="step-icon" />
                </div>
                <h4 className="step-title">{step.title}</h4>
                <p className="step-desc">{step.desc}</p>
              </div>
            );
          })}
        </div>
      </div>

      <style>{`
        .how-it-works-section {
          padding: 64px 0;
        }
        .pipeline-container {
          display: grid;
          grid-template-columns: repeat(6, 1fr);
          gap: 14px;
          margin-top: 24px;
        }
        .pipeline-step-card {
          padding: 24px 16px;
          text-align: center;
          display: flex;
          flex-direction: column;
          align-items: center;
          position: relative;
        }
        .step-badge {
          width: 30px;
          height: 30px;
          border-radius: 50%;
          background: linear-gradient(135deg, #1D4ED8 0%, #00D2FF 100%);
          color: #FFFFFF;
          font-weight: 700;
          font-size: 0.85rem;
          display: flex;
          align-items: center;
          justify-content: center;
          margin-bottom: 14px;
          box-shadow: 0 0 12px rgba(0, 210, 255, 0.4);
        }
        .step-icon-box {
          width: 48px;
          height: 48px;
          border-radius: 12px;
          background: rgba(30, 58, 138, 0.35);
          border: 1px solid rgba(56, 189, 248, 0.25);
          display: flex;
          align-items: center;
          justify-content: center;
          margin-bottom: 12px;
        }
        .step-icon {
          color: var(--accent-cyan);
        }
        .step-title {
          font-size: 1.02rem;
          font-weight: 700;
          color: #FFFFFF;
          margin-bottom: 8px;
        }
        .step-desc {
          font-size: 0.8rem;
          line-height: 1.5;
          color: var(--text-secondary);
        }

        @media (max-width: 1080px) {
          .pipeline-container {
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
          }
        }
        @media (max-width: 640px) {
          .pipeline-container {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </section>
  );
}

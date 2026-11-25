import React from 'react';
import { User, Scan, Crosshair, Grid3X3, Flame, Compass, AlertOctagon, Mail } from 'lucide-react';

const capabilitiesList = [
  {
    icon: User,
    title: "Person Detection",
    tag: "YOLOv8 Neural Network",
    description: "High-precision full-body person localization optimized with custom fine-tuned YOLOv8. Distinguishes individual pedestrians across challenging lighting, partial body occlusions, and varied stances."
  },
  {
    icon: Scan,
    title: "Head Detection",
    tag: "2×2 Spatial Tiling",
    description: "Specialized overhead head localization pipeline designed for high-density crowds and overhead CCTV angles where body silhouettes are occluded. Operates with batched spatial tiling."
  },
  {
    icon: Crosshair,
    title: "Multi-Object Tracking",
    tag: "DeepSORT + Kalman",
    description: "Continuous trajectory estimation using DeepSORT. Combines Kalman filter spatial velocity vectors with MobileNetV2 deep appearance embeddings to maintain consistent identity continuity across frames."
  },
  {
    icon: Grid3X3,
    title: "Crowd Density Analysis",
    tag: "Spatial Grid Mapping",
    description: "Dynamic spatial grid division quantifying localized occupancy, persons per grid cell, and rapid crowd influx rates to instantly identify hazardous over-saturation and bottleneck zones."
  },
  {
    icon: Flame,
    title: "Thermal Density Heatmaps",
    tag: "Real-Time Visualizer",
    description: "Dynamic 2D density heatmaps updated frame-by-frame using smooth OpenCV color blending. Visually highlights spatial bottlenecks, high-congestion corridors, and egress blockage."
  },
  {
    icon: Compass,
    title: "Motion & Anomaly Dynamics",
    tag: "Velocity Vector Tracking",
    description: "Advanced optical flow dynamics tracking average crowd speed, dominant directional heading, sudden panic/stampede running movements, and ego-motion compensation for camera movement."
  },
  {
    icon: AlertOctagon,
    title: "Multi-Factor Risk Engine",
    tag: "Composite Safety Score",
    description: "Algorithmic safety formulation synthesizing spatial density, crowd surge influx rate, and directional motion disorder into standardized Low, Medium, and High risk classifications."
  },
  {
    icon: Mail,
    title: "Automated Emergency Alerts",
    tag: "Firebase + SMTP Dispatch",
    description: "Automated multi-channel emergency notification dispatch: Firebase cloud sync, automated Gmail SMTP emails with spatial coordinates and camera metadata, and operator acknowledgment workflows."
  }
];

export default function Capabilities() {
  return (
    <section id="capabilities" className="capabilities-section">
      <div className="container">
        <div className="section-header">
          <div className="section-tag">Core Capabilities</div>
          <h2 className="section-title">Intelligent Crowd Surveillance Features</h2>
          <p className="section-desc">
            Engineered from the ground up for high-density public venues, major transit hubs, and mass civic gatherings.
          </p>
        </div>

        <div className="grid-4 capabilities-grid">
          {capabilitiesList.map((cap, index) => {
            const IconComponent = cap.icon;
            return (
              <div key={index} className="glass-card capability-card">
                <div className="cap-top">
                  <div className="cap-icon-box">
                    <IconComponent size={24} className="cap-icon" />
                  </div>
                  <span className="cap-tag">{cap.tag}</span>
                </div>
                <h3 className="cap-title">{cap.title}</h3>
                <p className="cap-desc">{cap.description}</p>
              </div>
            );
          })}
        </div>
      </div>

      <style>{`
        .capabilities-section {
          padding: 64px 0;
        }
        .capabilities-grid {
          margin-top: 24px;
        }
        .capability-card {
          padding: 26px 22px;
          display: flex;
          flex-direction: column;
          position: relative;
          overflow: hidden;
        }
        .capability-card::before {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 2px;
          background: linear-gradient(90deg, transparent, var(--accent-cyan), transparent);
          opacity: 0;
          transition: opacity 0.3s ease;
        }
        .capability-card:hover::before {
          opacity: 1;
        }
        .cap-top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 16px;
        }
        .cap-icon-box {
          width: 44px;
          height: 44px;
          border-radius: 12px;
          background: rgba(30, 58, 138, 0.35);
          border: 1px solid rgba(56, 189, 248, 0.25);
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .cap-icon {
          color: var(--accent-cyan);
        }
        .cap-tag {
          font-size: 0.72rem;
          font-weight: 600;
          color: var(--accent-blue);
          background: rgba(30, 58, 138, 0.3);
          border: 1px solid rgba(56, 189, 248, 0.2);
          padding: 3px 8px;
          border-radius: 6px;
        }
        .cap-title {
          font-size: 1.2rem;
          font-weight: 700;
          color: #FFFFFF;
          margin-bottom: 10px;
        }
        .cap-desc {
          font-size: 0.88rem;
          line-height: 1.6;
          color: var(--text-secondary);
        }
      `}</style>
    </section>
  );
}

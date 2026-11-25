import React from 'react';
import { Eye, Target, Sparkles, Image, Terminal, Server, Code, Database } from 'lucide-react';

const technologies = [
  {
    icon: Eye,
    name: "YOLOv8",
    role: "Object Detection Engine",
    desc: "State-of-the-art neural architecture fine-tuned for high-density crowds and overhead head localization with PyTorch inference."
  },
  {
    icon: Target,
    name: "DeepSORT",
    role: "Multi-Object Tracking",
    desc: "Deep association metric tracker leveraging Kalman filtering and cosine distance matching for persistent cross-frame track IDs."
  },
  {
    icon: Sparkles,
    name: "MobileNetV2",
    role: "Deep Embeddings",
    desc: "Lightweight deep convolutional neural backbone generating 128-dimensional appearance vectors for persistent pedestrian re-identification."
  },
  {
    icon: Image,
    name: "OpenCV",
    role: "Computer Vision",
    desc: "Optimized vision library handling low-level frame acquisition, spatial tiling, affine transformations, and thermal heatmap color blending."
  },
  {
    icon: Terminal,
    name: "Python 3.14",
    role: "Core Engine Runtime",
    desc: "High-performance backend engine coordinating inference pipelines, thread-safe camera queues, and asynchronous alert dispatchers."
  },
  {
    icon: Server,
    name: "FastAPI",
    role: "High-Speed Backend",
    desc: "Asynchronous Python web server providing low-latency REST endpoints, WebSocket telemetry feeds, and multipart MJPEG video streams."
  },
  {
    icon: Code,
    name: "React 19 + Vite",
    role: "Reactive Frontend",
    desc: "Modern, responsive dark cybersecurity SaaS user interface delivering real-time telemetry charts, live video preview, and operator controls."
  },
  {
    icon: Database,
    name: "Firebase RTDB",
    role: "Cloud Synchronization",
    desc: "Google Cloud NoSQL realtime database providing instant multi-client telemetry broadcast, historical logs, and remote command alerting."
  }
];

export default function TechStack() {
  return (
    <section id="tech-stack" className="tech-section">
      <div className="container">
        <div className="section-header">
          <div className="section-tag">Technology Foundation</div>
          <h2 className="section-title">Powered by Cutting-Edge Engineering</h2>
          <p className="section-desc">
            Combining industry-standard computer vision models with high-throughput cloud and web frameworks.
          </p>
        </div>

        <div className="grid-4 tech-grid">
          {technologies.map((tech, index) => {
            const IconComponent = tech.icon;
            return (
              <div key={index} className="glass-card tech-card">
                <div className="tech-icon-box">
                  <IconComponent size={24} className="tech-icon" />
                </div>
                <div className="tech-info">
                  <h4 className="tech-name">{tech.name}</h4>
                  <span className="tech-role">{tech.role}</span>
                  <p className="tech-desc">{tech.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <style>{`
        .tech-section {
          padding: 64px 0;
        }
        .tech-grid {
          margin-top: 24px;
        }
        .tech-card {
          padding: 24px 20px;
          display: flex;
          gap: 16px;
          align-items: flex-start;
        }
        .tech-icon-box {
          width: 44px;
          height: 44px;
          border-radius: 12px;
          background: rgba(30, 58, 138, 0.3);
          border: 1px solid rgba(56, 189, 248, 0.25);
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }
        .tech-icon {
          color: var(--accent-cyan);
        }
        .tech-info {
          display: flex;
          flex-direction: column;
        }
        .tech-name {
          font-size: 1.12rem;
          font-weight: 700;
          color: #FFFFFF;
          margin-bottom: 2px;
        }
        .tech-role {
          font-size: 0.74rem;
          font-weight: 600;
          color: var(--accent-blue);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-bottom: 8px;
        }
        .tech-desc {
          font-size: 0.84rem;
          color: var(--text-secondary);
          line-height: 1.5;
        }
      `}</style>
    </section>
  );
}

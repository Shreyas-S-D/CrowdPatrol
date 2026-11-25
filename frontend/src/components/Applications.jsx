import React from 'react';
import { Landmark, Music, Trophy, Train } from 'lucide-react';

const applications = [
  {
    icon: Landmark,
    title: "Public Gatherings",
    desc: "Political rallies, civic demonstrations, parades, and major religious pilgrimages where rapid crowd influx can create sudden, dangerous crushes in open streets."
  },
  {
    icon: Music,
    title: "Festivals & Concerts",
    desc: "High-energy music events, street carnivals, and cultural arenas featuring dynamic crowd movement, stage bottlenecks, and restricted perimeter gates."
  },
  {
    icon: Trophy,
    title: "Stadiums & Sports Arenas",
    desc: "Multi-tier sports complexes and entertainment arenas managing massive synchronized ingress, concession hall concourses, and rapid post-event egress."
  },
  {
    icon: Train,
    title: "Transport Hubs",
    desc: "Metro railway stations, international airports, railway platforms, and bus interchanges experiencing intense recurring commuter surges and platform choke points."
  }
];

export default function Applications() {
  return (
    <section id="applications" className="app-section">
      <div className="container">
        <div className="section-header">
          <div className="section-tag">Deployment Domains</div>
          <h2 className="section-title">Where CrowdPatrol Protects Lives</h2>
          <p className="section-desc">
            Tailored for high-stakes public environments where early intervention prevents catastrophic stampedes.
          </p>
        </div>

        <div className="grid-4 app-grid">
          {applications.map((app, idx) => {
            const IconComp = app.icon;
            return (
              <div key={idx} className="glass-card app-card">
                <div className="app-icon-box">
                  <IconComp size={28} className="app-icon" />
                </div>
                <h4 className="app-title">{app.title}</h4>
                <p className="app-desc">{app.desc}</p>
              </div>
            );
          })}
        </div>
      </div>

      <style>{`
        .app-section {
          padding: 64px 0;
        }
        .app-grid {
          margin-top: 24px;
        }
        .app-card {
          padding: 28px 22px;
          display: flex;
          flex-direction: column;
        }
        .app-icon-box {
          width: 52px;
          height: 52px;
          border-radius: 14px;
          background: rgba(30, 58, 138, 0.35);
          border: 1px solid rgba(56, 189, 248, 0.25);
          display: flex;
          align-items: center;
          justify-content: center;
          margin-bottom: 18px;
        }
        .app-icon {
          color: var(--accent-cyan);
        }
        .app-title {
          font-size: 1.2rem;
          font-weight: 700;
          color: #FFFFFF;
          margin-bottom: 10px;
        }
        .app-desc {
          font-size: 0.9rem;
          color: var(--text-secondary);
          line-height: 1.6;
        }
      `}</style>
    </section>
  );
}

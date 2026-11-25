import React, { useState } from 'react';
import { Shield, LayoutDashboard, Menu, X } from 'lucide-react';

export default function Navbar({ onLaunchDashboard }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header className="navbar-wrapper">
      <div className="container">
        <div className="navbar-container">
          {/* Brand Logo */}
          <a href="#hero" className="brand-logo">
            <div className="brand-icon-box">
              <Shield size={22} className="shield-icon" />
            </div>
            <div className="brand-text-group">
              <div className="brand-title">
                Crowd<span className="brand-accent">Patrol</span>
              </div>
              <span className="brand-sub">AI SURVEILLANCE SUITE</span>
            </div>
          </a>

          {/* Desktop Navigation Links */}
          <nav className="nav-desktop">
            <a href="#hero" className="nav-link">Home</a>
            <a href="#overview" className="nav-link">Overview</a>
            <a href="#capabilities" className="nav-link">Capabilities</a>
            <a href="#how-it-works" className="nav-link">Architecture</a>
            <a href="#tech-stack" className="nav-link">Technology</a>
            <a href="#applications" className="nav-link">Applications</a>
          </nav>

          {/* Action CTA */}
          <div className="nav-actions">
            <button onClick={onLaunchDashboard} className="btn-primary nav-cta-btn">
              <LayoutDashboard size={18} />
              <span>Launch Dashboard</span>
            </button>

            {/* Mobile Hamburger Button */}
            <button 
              className="mobile-menu-btn"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
          </div>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="mobile-dropdown">
            <a href="#hero" onClick={() => setMobileMenuOpen(false)} className="mobile-link">Home</a>
            <a href="#overview" onClick={() => setMobileMenuOpen(false)} className="mobile-link">Overview</a>
            <a href="#capabilities" onClick={() => setMobileMenuOpen(false)} className="mobile-link">Capabilities</a>
            <a href="#how-it-works" onClick={() => setMobileMenuOpen(false)} className="mobile-link">Architecture</a>
            <a href="#tech-stack" onClick={() => setMobileMenuOpen(false)} className="mobile-link">Technology</a>
            <a href="#applications" onClick={() => setMobileMenuOpen(false)} className="mobile-link">Applications</a>
            <button 
              onClick={() => { setMobileMenuOpen(false); onLaunchDashboard(); }}
              className="btn-primary mobile-cta-btn"
            >
              <LayoutDashboard size={18} />
              <span>Launch Dashboard</span>
            </button>
          </div>
        )}
      </div>

      <style>{`
        .navbar-wrapper {
          position: sticky;
          top: 16px;
          z-index: 100;
          margin-bottom: 24px;
        }
        .navbar-container {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 24px;
          background: rgba(11, 19, 38, 0.82);
          backdrop-filter: blur(14px);
          -webkit-backdrop-filter: blur(14px);
          border: 1px solid var(--border-color);
          border-radius: 18px;
          box-shadow: 0 10px 30px -4px rgba(0, 0, 0, 0.5);
        }
        .brand-logo {
          display: flex;
          align-items: center;
          gap: 12px;
          text-decoration: none;
        }
        .brand-icon-box {
          width: 40px;
          height: 40px;
          border-radius: 10px;
          background: linear-gradient(135deg, #1D4ED8 0%, #00D2FF 100%);
          display: flex;
          align-items: center;
          justify-content: center;
          color: #FFFFFF;
          box-shadow: 0 0 16px rgba(0, 210, 255, 0.45);
        }
        .brand-text-group {
          display: flex;
          flex-direction: column;
        }
        .brand-title {
          font-size: 1.35rem;
          font-weight: 800;
          letter-spacing: -0.02em;
          color: #FFFFFF;
          line-height: 1.2;
        }
        .brand-accent {
          color: var(--accent-cyan);
        }
        .brand-sub {
          font-size: 0.62rem;
          font-weight: 700;
          letter-spacing: 0.1em;
          color: var(--accent-blue);
        }
        .nav-desktop {
          display: flex;
          align-items: center;
          gap: 20px;
        }
        .nav-link {
          color: var(--text-secondary);
          font-size: 0.92rem;
          font-weight: 500;
          text-decoration: none;
          padding: 6px 10px;
          border-radius: 8px;
          transition: all 0.2s ease;
        }
        .nav-link:hover {
          color: var(--accent-blue);
          background: rgba(56, 189, 248, 0.08);
        }
        .nav-actions {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .nav-cta-btn {
          padding: 9px 18px;
          font-size: 0.9rem;
        }
        .mobile-menu-btn {
          display: none;
          background: transparent;
          border: none;
          color: #FFFFFF;
          cursor: pointer;
          padding: 6px;
        }
        .mobile-dropdown {
          display: none;
        }
        @media (max-width: 960px) {
          .nav-desktop {
            display: none;
          }
          .mobile-menu-btn {
            display: flex;
          }
          .mobile-dropdown {
            display: flex;
            flex-direction: column;
            gap: 12px;
            padding: 20px;
            background: rgba(11, 19, 38, 0.95);
            backdrop-filter: blur(16px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            margin-top: 10px;
          }
          .mobile-link {
            color: var(--text-secondary);
            font-size: 1rem;
            text-decoration: none;
            padding: 8px 12px;
            border-radius: 8px;
          }
          .mobile-link:hover {
            color: var(--accent-blue);
            background: rgba(56, 189, 248, 0.1);
          }
          .mobile-cta-btn {
            margin-top: 8px;
            width: 100%;
          }
        }
      `}</style>
    </header>
  );
}

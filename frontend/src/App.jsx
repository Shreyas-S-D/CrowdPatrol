import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Overview from './components/Overview';
import Capabilities from './components/Capabilities';
import HowItWorks from './components/HowItWorks';
import TechStack from './components/TechStack';
import Applications from './components/Applications';
import Footer from './components/Footer';
import Dashboard from './components/Dashboard';

export default function App() {
  const [currentView, setCurrentView] = useState('landing');

  // Sync with URL query parameter or hash if present
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('view') === 'dashboard') {
      setCurrentView('dashboard');
    }
  }, []);

  const handleLaunchDashboard = () => {
    setCurrentView('dashboard');
    window.scrollTo({ top: 0, behavior: 'smooth' });
    const url = new URL(window.location.href);
    url.searchParams.set('view', 'dashboard');
    window.history.pushState({}, '', url);
  };

  const handleReturnHome = () => {
    setCurrentView('landing');
    window.scrollTo({ top: 0, behavior: 'smooth' });
    const url = new URL(window.location.href);
    url.searchParams.delete('view');
    window.history.pushState({}, '', url);
  };

  return (
    <div className="app-layout">
      {currentView === 'landing' ? (
        <main className="landing-page-flow">
          <Navbar onLaunchDashboard={handleLaunchDashboard} />
          <Hero onLaunchDashboard={handleLaunchDashboard} />
          <Overview />
          <Capabilities />
          <HowItWorks />
          <TechStack />
          <Applications />
          <Footer onLaunchDashboard={handleLaunchDashboard} />
        </main>
      ) : (
        <main className="dashboard-page-flow">
          <Dashboard onReturnHome={handleReturnHome} />
        </main>
      )}

      <style>{`
        .app-layout {
          min-height: 100vh;
          display: flex;
          flex-direction: column;
        }
        .landing-page-flow {
          flex: 1;
        }
        .dashboard-page-flow {
          flex: 1;
        }
      `}</style>
    </div>
  );
}

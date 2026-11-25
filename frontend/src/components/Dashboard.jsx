import React, { useState, useEffect, useCallback } from 'react';
import {
  LayoutDashboard,
  Video,
  AlertTriangle,
  Activity,
  Settings,
  ArrowLeft,
  ShieldCheck,
  ShieldAlert,
  Play,
  Square,
  RefreshCw,
  Users,
  Flame,
  Compass,
  Mail,
  CheckCircle2,
  XCircle,
  Clock,
  Sliders,
  Eye,
  Camera,
  Wifi,
  WifiOff,
  Info,
  Send,
  Radio,
  FileText,
  Maximize2,
  Grid,
  Monitor,
  RotateCw,
  Layers
} from 'lucide-react';
import { api } from '../services/api';

export default function Dashboard({ onReturnHome }) {
  // Navigation State
  const [activeTab, setActiveTab] = useState('overview');

  // Live CCTV Layout & Streaming State
  const [monitoringLayout, setMonitoringLayout] = useState('grid'); // 'grid' | 'focus' | 'composite'
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [streamNonce, setStreamNonce] = useState(() => Date.now().toString());
  const [streamErrors, setStreamErrors] = useState({});

  // Backend Data State (Directly populated from real FastAPI REST endpoints)
  const [systemStatus, setSystemStatus] = useState({
    is_running: false,
    operating_mode: 'GRID',
    detection_mode: 'PERSON',
    tiled_mode: false,
    focus_camera: 'CAM-01',
    fps: 0.0,
    person_count: 0,
    risk_level: 'Low',
    active_alerts_count: 0,
    firebase_connected: false,
  });

  const [visionConfig, setVisionConfig] = useState({
    detection_mode: 'PERSON',
    tiled_mode: false,
    confidence: 0.25,
    detect_interval: 2,
    operating_mode: 'GRID',
    focus_camera: 'CAM-01',
  });

  const [camerasData, setCamerasData] = useState({
    configured_cameras: [],
    discovered_devices: [],
    sample_videos: [],
    live_status: {},
  });

  const [analyticsData, setAnalyticsData] = useState({
    current: {},
    history: {
      timestamps: [],
      risk_scores: [],
      person_counts: [],
      densities: [],
    },
    cameras_status: {},
  });

  const [alertsData, setAlertsData] = useState({
    active_alerts: [],
    history: [],
  });

  const [notificationsLog, setNotificationsLog] = useState([]);

  // UI & Network Feedback State
  const [loading, setLoading] = useState(true);
  const [backendOnline, setBackendOnline] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);
  const [actionNotice, setActionNotice] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Settings Form State
  const [settingsForm, setSettingsForm] = useState({
    detection_mode: 'PERSON',
    tiled_mode: false,
    confidence: 0.25,
    detect_interval: 2,
  });

  // Test Email & Camera Test Inputs
  const [testEmailInput, setTestEmailInput] = useState('');
  const [testCameraSourceInput, setTestCameraSourceInput] = useState('0');
  const [testCameraResult, setTestCameraResult] = useState(null);

  // Phone URL Generator State
  const [phoneIp, setPhoneIp] = useState('192.168.1.100');
  const [phonePort, setPhonePort] = useState(8080);
  const [generatedPhoneUrl, setGeneratedPhoneUrl] = useState('');

  // Camera Management Form State
  const [editingCameraId, setEditingCameraId] = useState(null);
  const [cameraForm, setCameraForm] = useState({
    id: '',
    name: '',
    source: '',
    source_type: 'video',
    enabled: true
  });

  // Primary Fetch Function (Queries all 6 required FastAPI endpoints)
  const fetchDashboardData = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);

    try {
      const [
        statusRes,
        configRes,
        camerasRes,
        analyticsRes,
        alertsRes,
        notificationsRes
      ] = await Promise.allSettled([
        api.getStatus(),
        api.getConfig(),
        api.getCameras(),
        api.getAnalyticsSummary(),
        api.getAlerts(50),
        api.getNotificationLog(50),
      ]);

      // Check if primary status endpoint connected
      if (statusRes.status === 'fulfilled') {
        setSystemStatus(statusRes.value);
        setBackendOnline(true);
        setErrorMessage(null);
      } else {
        setBackendOnline(false);
        setErrorMessage(statusRes.reason?.message || 'Cannot connect to FastAPI backend at http://localhost:8000');
      }

      // Populate config
      if (configRes.status === 'fulfilled') {
        setVisionConfig(configRes.value);
        setSettingsForm({
          detection_mode: configRes.value.detection_mode || 'PERSON',
          tiled_mode: Boolean(configRes.value.tiled_mode),
          confidence: configRes.value.confidence !== undefined ? configRes.value.confidence : 0.25,
          detect_interval: configRes.value.detect_interval || 2,
        });
      }

      // Populate cameras
      if (camerasRes.status === 'fulfilled') {
        setCamerasData(camerasRes.value);
      }

      // Populate analytics
      if (analyticsRes.status === 'fulfilled') {
        setAnalyticsData(analyticsRes.value);
      }

      // Populate alerts
      if (alertsRes.status === 'fulfilled') {
        setAlertsData(alertsRes.value);
      }

      // Populate notifications log
      if (notificationsRes.status === 'fulfilled') {
        setNotificationsLog(Array.isArray(notificationsRes.value) ? notificationsRes.value : []);
      }

      setLastRefreshed(new Date().toLocaleTimeString());
    } catch (err) {
      setBackendOnline(false);
      setErrorMessage(err.message || 'Error communicating with CrowdPatrol AI backend.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial mount fetch and periodic polling (every 3.5 seconds)
  useEffect(() => {
    fetchDashboardData(false);

    const intervalId = setInterval(() => {
      fetchDashboardData(true);
    }, 3500);

    return () => clearInterval(intervalId);
  }, [fetchDashboardData]);

  // Handle Pipeline Monitoring Start/Stop
  const handleToggleMonitoring = async () => {
    setActionLoading(true);
    setActionNotice(null);
    try {
      if (systemStatus.is_running) {
        const res = await api.stopMonitoring();
        setActionNotice({ type: 'success', text: res.message || 'Monitoring pipeline stopped.' });
      } else {
        const res = await api.startMonitoring();
        setActionNotice({ type: 'success', text: res.message || 'Monitoring pipeline started.' });
      }
      await fetchDashboardData(true);
    } catch (err) {
      setActionNotice({ type: 'error', text: err.message || 'Failed to toggle monitoring pipeline.' });
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Focus Camera Change
  const handleSetFocus = async (cameraId, autoSwitchToFocus = false) => {
    try {
      await api.setFocusCamera(cameraId);
      if (autoSwitchToFocus) {
        setMonitoringLayout('focus');
        try {
          await api.setCameraLayout('FOCUS', cameraId);
        } catch {
          // Non-fatal
        }
      }
      setActionNotice({ type: 'success', text: `Switched focus to camera ${cameraId}` });
      await fetchDashboardData(true);
    } catch (err) {
      setActionNotice({ type: 'error', text: err.message || `Failed to switch focus to ${cameraId}` });
    }
  };

  // Handle CCTV Layout Switch
  const handleSwitchLayout = async (layout, focusCam = null) => {
    setMonitoringLayout(layout);
    try {
      await api.setCameraLayout(layout === 'focus' ? 'FOCUS' : 'GRID', focusCam || systemStatus.focus_camera);
      await fetchDashboardData(true);
    } catch {
      // Non-fatal
    }
  };

  // Handle Stream Reconnect
  const handleReconnectStreams = () => {
    setStreamNonce(Date.now().toString());
    setStreamErrors({});
    setActionNotice({ type: 'success', text: 'Reconnecting live CCTV streams...' });
  };

  // Stream Error & Success Handlers
  const handleStreamError = (id) => {
    setStreamErrors(prev => ({ ...prev, [id]: true }));
  };

  const handleStreamSuccess = (id) => {
    setStreamErrors(prev => {
      if (!prev[id]) return prev;
      const copy = { ...prev };
      delete copy[id];
      return copy;
    });
  };

  // Handle Alert Acknowledge
  const handleAcknowledgeAlert = async (cameraId) => {
    try {
      const res = await api.acknowledgeAlert(cameraId, 'WebOperator');
      setActionNotice({ type: 'success', text: res.message || `Alert for ${cameraId} acknowledged.` });
      await fetchDashboardData(true);
    } catch (err) {
      setActionNotice({ type: 'error', text: err.message || `Failed to acknowledge alert for ${cameraId}` });
    }
  };

  // Handle Alert Resolve
  const handleResolveAlert = async (cameraId) => {
    try {
      const res = await api.resolveAlert(cameraId, 'WebOperator', 'Resolved via Web Dashboard');
      setActionNotice({ type: 'success', text: res.message || `Alert for ${cameraId} resolved.` });
      await fetchDashboardData(true);
    } catch (err) {
      setActionNotice({ type: 'error', text: err.message || `Failed to resolve alert for ${cameraId}` });
    }
  };

  // Handle Save Vision Config
  const handleSaveConfig = async (e) => {
    e.preventDefault();
    setActionLoading(true);
    setActionNotice(null);
    try {
      const res = await api.updateConfig({
        detection_mode: settingsForm.detection_mode,
        tiled_mode: settingsForm.tiled_mode,
        confidence: parseFloat(settingsForm.confidence),
        detect_interval: parseInt(settingsForm.detect_interval, 10),
      });
      setActionNotice({ type: 'success', text: `Configuration updated: ${res.detection_mode} mode active.` });
      await fetchDashboardData(true);
    } catch (err) {
      setActionNotice({ type: 'error', text: err.message || 'Failed to update configuration.' });
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Send Test Email
  const handleSendTestEmail = async (e) => {
    e.preventDefault();
    setActionLoading(true);
    setActionNotice(null);
    try {
      const res = await api.sendTestEmail(testEmailInput.trim() || null);
      if (res.success) {
        setActionNotice({ type: 'success', text: res.message || 'Test email dispatched successfully.' });
        setTestEmailInput('');
      } else {
        setActionNotice({ type: 'error', text: res.message || 'Test email dispatch failed.' });
      }
      await fetchDashboardData(true);
    } catch (err) {
      setActionNotice({ type: 'error', text: err.message || 'Test email dispatch failed.' });
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Test Camera Source
  const handleTestCamera = async (e) => {
    e.preventDefault();
    setActionLoading(true);
    setTestCameraResult(null);
    try {
      const res = await api.testCameraSource(testCameraSourceInput.trim());
      setTestCameraResult(res);
    } catch (err) {
      setTestCameraResult({ success: false, message: err.message || 'Connection test failed.' });
    } finally {
      setActionLoading(false);
    }
  };

  // Helper for generating Phone URL
  const handleGeneratePhoneUrl = () => {
    const port = phonePort || 8080;
    const url = `http://${phoneIp.trim()}:${port}/video`;
    setGeneratedPhoneUrl(url);
  };

  // Camera Management Handlers
  const handleEditCamera = (cam) => {
    setEditingCameraId(cam.id);
    setCameraForm({
      id: cam.id,
      name: cam.name || cam.id,
      source: String(cam.source),
      source_type: cam.source_type || 'video',
      enabled: cam.enabled !== false
    });
  };

  const handleSaveCamera = async (e) => {
    e.preventDefault();
    setActionLoading(true);
    setActionNotice(null);
    try {
      const res = await api.reconfigureCamera({
        camera_id: cameraForm.id,
        name: cameraForm.name,
        source: cameraForm.source,
        source_type: cameraForm.source_type,
        enabled: cameraForm.enabled
      });
      setActionNotice({ type: 'success', text: `Camera ${cameraForm.id} updated successfully (${res.status || 'Active'})` });
      setEditingCameraId(null);
      await fetchDashboardData(true);
    } catch (err) {
      setActionNotice({ type: 'error', text: err.message || 'Failed to update camera source' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteCamera = async (camId) => {
    if (!window.confirm(`Are you sure you want to remove ${camId}?`)) return;
    setActionLoading(true);
    try {
      await api.deleteCamera(camId);
      setActionNotice({ type: 'success', text: `Camera ${camId} removed cleanly` });
      await fetchDashboardData(true);
    } catch (err) {
      setActionNotice({ type: 'error', text: err.message || 'Failed to remove camera' });
    } finally {
      setActionLoading(false);
    }
  };

  // Risk Level Color Utility
  const getRiskColor = (level) => {
    switch (String(level).toLowerCase()) {
      case 'critical': return 'var(--danger)';
      case 'high': return '#f97316';
      case 'medium': return 'var(--warning)';
      default: return 'var(--success)';
    }
  };

  return (
    <div className="dashboard-container">
      {/* Top Header Bar */}
      <header className="dashboard-header glass-card">
        <div className="header-left">
          <button onClick={onReturnHome} className="btn-secondary return-btn" title="Back to CrowdPatrol Landing Page">
            <ArrowLeft size={16} />
            <span>Landing Page</span>
          </button>
          <div className="header-divider"></div>
          <div className="header-branding">
            <div className="system-status-indicator">
              <span
                className="status-dot"
                style={{
                  backgroundColor: !backendOnline
                    ? 'var(--danger)'
                    : systemStatus.is_running
                    ? 'var(--success)'
                    : 'var(--accent-cyan)'
                }}
              ></span>
              <span className="status-text">
                {!backendOnline
                  ? 'BACKEND OFFLINE'
                  : systemStatus.is_running
                  ? 'AI PIPELINE RUNNING'
                  : 'PIPELINE STANDBY'}
              </span>
            </div>
            <h1 className="header-title">CrowdPatrol Command Center</h1>
          </div>
        </div>

        <div className="header-right">
          {/* Active Mode Badge */}
          <div className="header-badge mode-badge">
            <Radio size={14} className="badge-icon" />
            <span>MODE: {systemStatus.detection_mode || 'PERSON'}</span>
          </div>

          {/* Firebase Sync Badge */}
          <div className="header-badge firebase-badge">
            {systemStatus.firebase_connected ? (
              <>
                <Wifi size={14} className="badge-icon text-success" />
                <span>Cloud Connected</span>
              </>
            ) : (
              <>
                <WifiOff size={14} className="badge-icon text-warning" />
                <span>Offline Fallback</span>
              </>
            )}
          </div>

          {/* Manual Refresh Button */}
          <button
            onClick={() => fetchDashboardData(false)}
            className="btn-icon"
            title={`Last refreshed at ${lastRefreshed || 'Connecting...'}`}
            disabled={loading}
          >
            <RefreshCw size={16} className={loading ? 'spinning' : ''} />
          </button>

          {/* Monitoring Start / Stop Master Button */}
          <button
            onClick={handleToggleMonitoring}
            className={systemStatus.is_running ? 'btn-danger' : 'btn-primary'}
            disabled={!backendOnline || actionLoading}
          >
            {systemStatus.is_running ? (
              <>
                <Square size={16} />
                <span>Stop Monitoring</span>
              </>
            ) : (
              <>
                <Play size={16} />
                <span>Start Monitoring</span>
              </>
            )}
          </button>
        </div>
      </header>

      {/* Global Notification / Alert Banner */}
      {actionNotice && (
        <div className={`notice-banner ${actionNotice.type === 'error' ? 'notice-error' : 'notice-success'}`}>
          <div className="notice-content">
            {actionNotice.type === 'error' ? <XCircle size={18} /> : <CheckCircle2 size={18} />}
            <span>{actionNotice.text}</span>
          </div>
          <button onClick={() => setActionNotice(null)} className="notice-close">✕</button>
        </div>
      )}

      {/* Offline Warning Banner */}
      {!backendOnline && (
        <div className="notice-banner notice-error">
          <div className="notice-content">
            <WifiOff size={18} />
            <span>
              <strong>CrowdPatrol AI Backend Disconnected:</strong> FastAPI server is not responding at{' '}
              <code>http://localhost:8000</code>. Verify that <code>python -m uvicorn backend.main:app --port 8000</code> is running.
            </span>
          </div>
          <button onClick={() => fetchDashboardData(false)} className="btn-secondary btn-sm">
            Retry Connection
          </button>
        </div>
      )}

      {/* Dashboard Body with Sidebar & Content */}
      <div className="dashboard-body">
        {/* Sidebar Navigation */}
        <aside className="dashboard-sidebar glass-card">
          <nav className="sidebar-nav">
            <button
              onClick={() => setActiveTab('overview')}
              className={`sidebar-tab ${activeTab === 'overview' ? 'active' : ''}`}
            >
              <LayoutDashboard size={18} />
              <span>Overview</span>
            </button>

            <button
              onClick={() => setActiveTab('monitoring')}
              className={`sidebar-tab ${activeTab === 'monitoring' ? 'active' : ''}`}
            >
              <Video size={18} />
              <span>Live Monitoring</span>
            </button>

            <button
              onClick={() => setActiveTab('alerts')}
              className={`sidebar-tab ${activeTab === 'alerts' ? 'active' : ''}`}
            >
              <AlertTriangle size={18} />
              <span>Emergency Alerts</span>
              {systemStatus.active_alerts_count > 0 && (
                <span className="sidebar-alert-badge">{systemStatus.active_alerts_count}</span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('analytics')}
              className={`sidebar-tab ${activeTab === 'analytics' ? 'active' : ''}`}
            >
              <Activity size={18} />
              <span>Analytics & Trends</span>
            </button>

            <button
              onClick={() => setActiveTab('settings')}
              className={`sidebar-tab ${activeTab === 'settings' ? 'active' : ''}`}
            >
              <Settings size={18} />
              <span>System Settings</span>
            </button>
          </nav>

          <div className="sidebar-footer">
            <div className="sidebar-info-box">
              <div className="info-row">
                <span className="info-key">Operating Mode:</span>
                <span className="info-val">{systemStatus.operating_mode}</span>
              </div>
              <div className="info-row">
                <span className="info-key">Focus Feed:</span>
                <span className="info-val">{systemStatus.focus_camera}</span>
              </div>
              <div className="info-row">
                <span className="info-key">Inference FPS:</span>
                <span className="info-val">{systemStatus.fps ? systemStatus.fps.toFixed(1) : '0.0'}</span>
              </div>
              <div className="info-row">
                <span className="info-key">Last Sync:</span>
                <span className="info-val">{lastRefreshed || 'Pending'}</span>
              </div>
            </div>
          </div>
        </aside>

        {/* Main Dashboard Content Area */}
        <main className="dashboard-content">
          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <div className="tab-pane overview-pane">
              {/* Primary Metric KPI Cards */}
              <div className="kpi-grid">
                <div className="glass-card kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-label">Pipeline Engine Status</span>
                    <Radio size={20} className={systemStatus.is_running ? 'text-success' : 'text-cyan'} />
                  </div>
                  <div className="kpi-value">
                    {systemStatus.is_running ? 'Running' : 'Standby'}
                  </div>
                  <div className="kpi-meta">
                    FPS: <strong>{systemStatus.fps ? systemStatus.fps.toFixed(1) : '0.0'}</strong> • Mode: <strong>{systemStatus.detection_mode}</strong>
                  </div>
                </div>

                <div className="glass-card kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-label">Tracked Crowd Count</span>
                    <Users size={20} className="text-cyan" />
                  </div>
                  <div className="kpi-value">
                    {systemStatus.person_count || 0}
                  </div>
                  <div className="kpi-meta">
                    Maximum Density: <strong>{analyticsData.current?.max_density ? analyticsData.current.max_density.toFixed(1) : '0.0'}</strong>
                  </div>
                </div>

                <div className="glass-card kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-label">Composite Risk Assessment</span>
                    <ShieldAlert size={20} style={{ color: getRiskColor(systemStatus.risk_level) }} />
                  </div>
                  <div className="kpi-value" style={{ color: getRiskColor(systemStatus.risk_level) }}>
                    {systemStatus.risk_level || 'Low'}
                  </div>
                  <div className="kpi-meta">
                    Score: <strong>{analyticsData.current?.combined_score || 0.0} / 100</strong>
                  </div>
                </div>

                <div className="glass-card kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-label">Active Emergencies</span>
                    <AlertTriangle size={20} className={systemStatus.active_alerts_count > 0 ? 'text-danger' : 'text-success'} />
                  </div>
                  <div className="kpi-value" style={{ color: systemStatus.active_alerts_count > 0 ? 'var(--danger)' : 'var(--text-primary)' }}>
                    {systemStatus.active_alerts_count || 0}
                  </div>
                  <div className="kpi-meta">
                    {systemStatus.firebase_connected ? 'Syncing to Cloud RTDB' : 'Local Offline Ledger'}
                  </div>
                </div>
              </div>

              {/* Monitored Camera Channels Grid */}
              <div className="overview-section-box">
                <div className="section-title-row">
                  <div className="title-left">
                    <Video size={18} />
                    <h3>Configured Surveillance Sectors</h3>
                  </div>
                  <span className="count-pill">
                    {camerasData.configured_cameras?.length || 0} Channels Configured
                  </span>
                </div>

                <div className="cam-channels-grid">
                  {camerasData.configured_cameras && camerasData.configured_cameras.length > 0 ? (
                    camerasData.configured_cameras.map((cam) => {
                      const isFocused = systemStatus.focus_camera === cam.id;
                      const liveInfo = camerasData.live_status?.[cam.id] || {};
                      return (
                        <div key={cam.id} className={`glass-card channel-card ${isFocused ? 'channel-focused' : ''}`}>
                          <div className="channel-top">
                            <span className="channel-name">{cam.name || cam.id}</span>
                            <span className={`channel-status-pill ${cam.enabled ? 'status-enabled' : 'status-disabled'}`}>
                              {cam.enabled ? 'Configured' : 'Disabled'}
                            </span>
                          </div>
                          <div className="channel-id-row">
                            <span className="badge-id">{cam.id}</span>
                            {isFocused && <span className="badge-focus">FOCUS FEED</span>}
                          </div>
                          <div className="channel-meta-box">
                            <div className="meta-line">
                              <span>Source:</span>
                              <span className="meta-val" title={String(cam.source)}>{String(cam.source)}</span>
                            </div>
                            <div className="meta-line">
                              <span>Type:</span>
                              <span className="meta-val">{cam.source_type || 'video'}</span>
                            </div>
                            <div className="meta-line">
                              <span>Resolution:</span>
                              <span className="meta-val">{liveInfo.width && liveInfo.height ? `${liveInfo.width}×${liveInfo.height}` : 'Standby'}</span>
                            </div>
                          </div>
                          <div className="channel-footer">
                            <button
                              onClick={() => handleSetFocus(cam.id)}
                              className={`btn-secondary btn-sm ${isFocused ? 'btn-focused' : ''}`}
                              disabled={isFocused}
                            >
                              {isFocused ? 'Active Focus' : 'Set as Focus Feed'}
                            </button>
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="glass-card empty-card">
                      <p>No configured cameras discovered in <code>cameras.json</code>.</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Recent Alerts Quick Ledger */}
              <div className="overview-section-box">
                <div className="section-title-row">
                  <div className="title-left">
                    <AlertTriangle size={18} />
                    <h3>Active & Recent Emergencies</h3>
                  </div>
                  <button onClick={() => setActiveTab('alerts')} className="btn-link">
                    View Full Alerts Ledger →
                  </button>
                </div>

                <div className="glass-card table-card">
                  {alertsData.active_alerts && alertsData.active_alerts.length > 0 ? (
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Camera</th>
                          <th>Severity</th>
                          <th>Hazard Description</th>
                          <th>Triggered At</th>
                          <th>Status</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {alertsData.active_alerts.map((alert, idx) => (
                          <tr key={idx} className="alert-row-active">
                            <td><strong>{alert.camera_id}</strong></td>
                            <td>
                              <span className="severity-pill" style={{ backgroundColor: getRiskColor(alert.severity) }}>
                                {alert.severity}
                              </span>
                            </td>
                            <td>{alert.reason || 'Hazard threshold exceeded'}</td>
                            <td>{alert.timestamp || 'N/A'}</td>
                            <td>
                              <span className="status-tag">
                                {alert.acknowledged ? 'Acknowledged' : 'Unacknowledged'}
                              </span>
                            </td>
                            <td>
                              <div className="table-actions">
                                {!alert.acknowledged && (
                                  <button
                                    onClick={() => handleAcknowledgeAlert(alert.camera_id)}
                                    className="btn-secondary btn-xs"
                                  >
                                    Acknowledge
                                  </button>
                                )}
                                <button
                                  onClick={() => handleResolveAlert(alert.camera_id)}
                                  className="btn-danger btn-xs"
                                >
                                  Resolve
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="nominal-state">
                      <ShieldCheck size={36} className="text-success" />
                      <h4>All Monitored Sectors Nominal</h4>
                      <p>No active emergencies, bottleneck crushes, or rapid influx warnings currently detected.</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: LIVE MONITORING */}
          {activeTab === 'monitoring' && (
            <div className="tab-pane monitoring-pane">
              {/* Surveillance Toolbar */}
              <div className="stream-toolbar glass-card">
                <div className="toolbar-left">
                  <span className="toolbar-label">LAYOUT:</span>
                  <div className="layout-btn-group">
                    <button
                      onClick={() => handleSwitchLayout('grid')}
                      className={`btn-toolbar ${monitoringLayout === 'grid' ? 'active' : ''}`}
                      title="2×2 Independent Camera Grid"
                    >
                      <Grid size={16} />
                      <span>2×2 Multi-Feed</span>
                    </button>
                    <button
                      onClick={() => handleSwitchLayout('composite')}
                      className={`btn-toolbar ${monitoringLayout === 'composite' ? 'active' : ''}`}
                      title="Unified 1280×720 Composite CCTV Grid"
                    >
                      <Monitor size={16} />
                      <span>Unified Composite</span>
                    </button>
                    <button
                      onClick={() => handleSwitchLayout('focus')}
                      className={`btn-toolbar ${monitoringLayout === 'focus' ? 'active' : ''}`}
                      title="Full Resolution Focus Feed"
                    >
                      <Maximize2 size={16} />
                      <span>Focus Feed</span>
                    </button>
                  </div>
                </div>

                {/* Focus Camera Quick Switcher Pills */}
                <div className="toolbar-center">
                  <span className="toolbar-label">SECTOR:</span>
                  <div className="cam-pill-group">
                    {['CAM-01', 'CAM-02', 'CAM-03', 'CAM-04'].map((cid) => {
                      const isFocused = systemStatus.focus_camera === cid;
                      return (
                        <button
                          key={cid}
                          onClick={() => handleSetFocus(cid, monitoringLayout === 'focus')}
                          className={`btn-cam-pill ${isFocused ? 'active-focus' : ''}`}
                        >
                          {cid}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Right Action Tools */}
                <div className="toolbar-right">
                  <button
                    onClick={() => setShowHeatmap(!showHeatmap)}
                    className={`btn-toolbar ${showHeatmap ? 'active-heatmap' : ''}`}
                    title="Toggle Thermal Density Heatmap View"
                  >
                    <Flame size={16} />
                    <span>{showHeatmap ? 'Hide Heatmap' : 'Thermal Heatmap'}</span>
                  </button>

                  <button
                    onClick={handleReconnectStreams}
                    className="btn-toolbar"
                    title="Force refresh stream connections"
                  >
                    <RotateCw size={16} />
                    <span>Reconnect Feeds</span>
                  </button>
                </div>
              </div>

              {/* LAYOUT 1: 2x2 MULTI-CAMERA INDEPENDENT GRID */}
              {monitoringLayout === 'grid' && (
                <div className="cctv-grid-container">
                  <div className="cctv-2x2-grid">
                    {['CAM-01', 'CAM-02', 'CAM-03', 'CAM-04'].map((camId) => {
                      const camConfig = camerasData.configured_cameras?.find(c => c.id === camId) || {
                        id: camId,
                        name: `Sector ${camId}`,
                        source: 'Standby Source',
                        source_type: 'video',
                        enabled: true
                      };
                      const isFocus = systemStatus.focus_camera === camId;
                      const liveInfo = camerasData.live_status?.[camId] || {};
                      const hasError = streamErrors[camId];

                      return (
                        <div key={camId} className={`glass-card cctv-cam-slot ${isFocus ? 'slot-focus' : ''}`}>
                          <div className="slot-header">
                            <div className="slot-title-group">
                              <span className={`live-dot ${systemStatus.is_running ? 'dot-pulse-live' : 'dot-standby'}`}></span>
                              <span className="slot-cam-name">{camConfig.name || camId}</span>
                            </div>
                            <div className="slot-badges">
                              {isFocus && <span className="focus-badge">FOCUS FEED</span>}
                              <span className="source-type-badge">{camConfig.source_type?.toUpperCase() || 'VIDEO'}</span>
                              <span className="id-badge">{camId}</span>
                            </div>
                          </div>

                          {/* Live Video Viewport */}
                          <div className="slot-viewport">
                            {systemStatus.is_running && !hasError ? (
                              <img
                                src={api.getCameraStreamUrl(camId, streamNonce)}
                                alt={`Live CCTV ${camId}`}
                                className="cctv-live-img"
                                onError={() => handleStreamError(camId)}
                                onLoad={() => handleStreamSuccess(camId)}
                              />
                            ) : (
                              <div className="stream-standby-overlay">
                                <Camera size={38} className="cam-center-icon" />
                                <div className="standby-title">
                                  {hasError ? 'Stream Disconnected' : 'CCTV Feed Standby'}
                                </div>
                                <div className="standby-desc">
                                  {hasError
                                    ? 'Lost connection to video stream chunk'
                                    : 'Pipeline capture is currently stopped'}
                                </div>
                                {hasError ? (
                                  <button onClick={() => handleStreamSuccess(camId)} className="btn-secondary btn-xs">
                                    <RotateCw size={12} />
                                    <span>Retry Stream</span>
                                  </button>
                                ) : (
                                  <button onClick={handleToggleMonitoring} className="btn-primary btn-xs">
                                    <Play size={12} />
                                    <span>Start Monitoring</span>
                                  </button>
                                )}
                              </div>
                            )}

                            {/* Viewport HUD Overlays */}
                            <div className="viewport-overlay-top">
                              <span className="overlay-tag">{camConfig.source_type?.toUpperCase() || 'VIDEO'}</span>
                              <span className="overlay-tag">
                                {systemStatus.is_running ? 'LIVE CAPTURE' : 'STANDBY'}
                              </span>
                            </div>

                            <div className="viewport-overlay-bottom">
                              <span>FPS: {systemStatus.is_running ? (systemStatus.fps ? systemStatus.fps.toFixed(1) : '30.0') : '0.0'}</span>
                              <span>Mode: {systemStatus.detection_mode}</span>
                              <span>{liveInfo.width && liveInfo.height ? `${liveInfo.width}×${liveInfo.height}` : '640×480'}</span>
                            </div>
                          </div>

                          {/* Slot Controls Footer */}
                          <div className="slot-footer">
                            <div className="slot-meta-info">
                              <span className="meta-text" title={String(camConfig.source)}>
                                Source: <strong>{String(camConfig.source)}</strong>
                              </span>
                            </div>
                            <div className="slot-btn-actions">
                              <button
                                onClick={() => handleSetFocus(camId, true)}
                                className="btn-secondary btn-sm"
                                title="Enlarge into Focus Feed"
                              >
                                <Maximize2 size={13} />
                                <span>Focus</span>
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* LAYOUT 2: FULL-SIZE FOCUS FEED */}
              {monitoringLayout === 'focus' && (
                <div className="cctv-focus-container">
                  <div className="glass-card focus-stream-card">
                    <div className="focus-header">
                      <div className="focus-title-group">
                        <span className={`live-dot ${systemStatus.is_running ? 'dot-pulse-live' : 'dot-standby'}`}></span>
                        <h3>
                          Focus Surveillance Stream: <strong>{systemStatus.focus_camera}</strong>
                          {showHeatmap && <span className="heatmap-active-pill">🔥 DENSITY HEATMAP ACTIVE</span>}
                        </h3>
                      </div>
                      <div className="focus-header-actions">
                        <button onClick={() => handleSwitchLayout('grid')} className="btn-secondary btn-sm">
                          <Grid size={14} />
                          <span>Switch to 2×2 Grid</span>
                        </button>
                      </div>
                    </div>

                    <div className="focus-viewport">
                      {systemStatus.is_running && !streamErrors['focus'] ? (
                        <img
                          src={showHeatmap ? api.getHeatmapStreamUrl(streamNonce) : api.getCameraStreamUrl(systemStatus.focus_camera || 'CAM-01', streamNonce)}
                          alt="Primary Focus CCTV Feed"
                          className="cctv-live-img"
                          onError={() => handleStreamError('focus')}
                          onLoad={() => handleStreamSuccess('focus')}
                        />
                      ) : (
                        <div className="stream-standby-overlay large-overlay">
                          <Camera size={54} className="cam-center-icon" />
                          <div className="standby-title">
                            {streamErrors['focus'] ? 'Focus Stream Disconnected' : 'Focus Feed Standby'}
                          </div>
                          <div className="standby-desc">
                            {streamErrors['focus']
                              ? 'Camera source could not be decoded. Click retry below.'
                              : 'Click "Start Monitoring" in the command header to begin AI inference.'}
                          </div>
                          {streamErrors['focus'] ? (
                            <button onClick={() => handleStreamSuccess('focus')} className="btn-secondary btn-sm">
                              <RotateCw size={14} />
                              <span>Reconnect Stream</span>
                            </button>
                          ) : (
                            <button onClick={handleToggleMonitoring} className="btn-primary btn-sm">
                              <Play size={14} />
                              <span>Start Monitoring</span>
                            </button>
                          )}
                        </div>
                      )}

                      {/* Focus HUD Overlay */}
                      <div className="viewport-overlay-top">
                        <span className="overlay-tag-large">
                          {systemStatus.focus_camera} • {showHeatmap ? 'SPATIAL DENSITY HEATMAP' : 'YOLOv8 + DeepSORT'}
                        </span>
                        <span className="overlay-tag-large">
                          {systemStatus.is_running ? 'LIVE PIPELINE' : 'STANDBY'}
                        </span>
                      </div>

                      <div className="viewport-overlay-bottom">
                        <span>FPS: {systemStatus.is_running ? (systemStatus.fps ? systemStatus.fps.toFixed(1) : '30.0') : '0.0'}</span>
                        <span>Mode: {systemStatus.detection_mode}</span>
                        <span>Tracks: {systemStatus.person_count || 0}</span>
                        <span>Risk: {systemStatus.risk_level}</span>
                      </div>
                    </div>

                    {/* Focus Telemetry HUD Bar */}
                    <div className="focus-telemetry-hud">
                      <div className="hud-metric">
                        <span className="hud-label">Monitored Sector</span>
                        <span className="hud-value">{systemStatus.focus_camera}</span>
                      </div>
                      <div className="hud-metric">
                        <span className="hud-label">Tracked Count</span>
                        <span className="hud-value text-cyan">{systemStatus.person_count || 0}</span>
                      </div>
                      <div className="hud-metric">
                        <span className="hud-label">Peak Density</span>
                        <span className="hud-value">{analyticsData.current?.max_density ? analyticsData.current.max_density.toFixed(1) : '0.0'}</span>
                      </div>
                      <div className="hud-metric">
                        <span className="hud-label">Avg Speed</span>
                        <span className="hud-value">{analyticsData.current?.avg_speed ? `${analyticsData.current.avg_speed.toFixed(1)} px/s` : '0.0 px/s'}</span>
                      </div>
                      <div className="hud-metric">
                        <span className="hud-label">Motion Direction</span>
                        <span className="hud-value">{analyticsData.current?.dominant_direction || 'STATIC'}</span>
                      </div>
                      <div className="hud-metric">
                        <span className="hud-label">Risk Level</span>
                        <span className="hud-value" style={{ color: getRiskColor(systemStatus.risk_level) }}>
                          {systemStatus.risk_level || 'Low'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* LAYOUT 3: UNIFIED 1280x720 COMPOSITE CCTV GRID */}
              {monitoringLayout === 'composite' && (
                <div className="cctv-composite-container">
                  <div className="glass-card composite-card">
                    <div className="focus-header">
                      <div className="focus-title-group">
                        <span className={`live-dot ${systemStatus.is_running ? 'dot-pulse-live' : 'dot-standby'}`}></span>
                        <h3>Unified 4-Channel Composite CCTV Grid (1280×720)</h3>
                      </div>
                      <div className="focus-header-actions">
                        <button onClick={() => handleSwitchLayout('grid')} className="btn-secondary btn-sm">
                          <Grid size={14} />
                          <span>Switch to 2×2 Multi-Feed</span>
                        </button>
                      </div>
                    </div>

                    <div className="composite-viewport">
                      {systemStatus.is_running && !streamErrors['composite'] ? (
                        <img
                          src={api.getLiveStreamUrl('grid', streamNonce)}
                          alt="Unified 4-Channel CCTV Grid"
                          className="cctv-live-img"
                          onError={() => handleStreamError('composite')}
                          onLoad={() => handleStreamSuccess('composite')}
                        />
                      ) : (
                        <div className="stream-standby-overlay large-overlay">
                          <Camera size={54} className="cam-center-icon" />
                          <div className="standby-title">
                            {streamErrors['composite'] ? 'Composite Grid Disconnected' : 'Composite Grid Standby'}
                          </div>
                          <div className="standby-desc">
                            Click "Start Monitoring" in the command header to activate unified capture.
                          </div>
                          <button onClick={handleToggleMonitoring} className="btn-primary btn-sm">
                            <Play size={14} />
                            <span>Start Monitoring</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: ALERTS */}
          {activeTab === 'alerts' && (
            <div className="tab-pane alerts-pane">
              {/* Active Alerts Section */}
              <div className="alerts-section">
                <div className="section-title-row">
                  <div className="title-left">
                    <AlertTriangle size={20} className="text-danger" />
                    <h3>Active Emergency Alerts</h3>
                  </div>
                  <span className="count-pill">
                    {alertsData.active_alerts?.length || 0} Requiring Action
                  </span>
                </div>

                <div className="active-alerts-list">
                  {alertsData.active_alerts && alertsData.active_alerts.length > 0 ? (
                    alertsData.active_alerts.map((alert, idx) => (
                      <div key={idx} className="glass-card active-alert-card">
                        <div className="alert-card-left">
                          <div className="severity-indicator" style={{ backgroundColor: getRiskColor(alert.severity) }}></div>
                          <div className="alert-card-info">
                            <div className="alert-card-header">
                              <span className="alert-cam-pill">{alert.camera_id}</span>
                              <span className="severity-badge" style={{ backgroundColor: getRiskColor(alert.severity) }}>
                                {alert.severity} SEVERITY
                              </span>
                              <span className="alert-timestamp">
                                <Clock size={14} />
                                {alert.timestamp || 'Just now'}
                              </span>
                            </div>
                            <h4 className="alert-reason-title">{alert.reason || 'Hazardous condition detected'}</h4>
                            <div className="alert-details-row">
                              <span>Risk Score: <strong>{alert.score ? alert.score.toFixed(1) : 'N/A'}</strong></span>
                              <span>Crowd Count: <strong>{alert.person_count || 'N/A'}</strong></span>
                              <span>Status: <strong>{alert.acknowledged ? 'Acknowledged' : 'Needs Operator Review'}</strong></span>
                            </div>
                          </div>
                        </div>

                        <div className="alert-card-actions">
                          {!alert.acknowledged && (
                            <button
                              onClick={() => handleAcknowledgeAlert(alert.camera_id)}
                              className="btn-secondary"
                            >
                              <CheckCircle2 size={16} />
                              <span>Acknowledge</span>
                            </button>
                          )}
                          <button
                            onClick={() => handleResolveAlert(alert.camera_id)}
                            className="btn-danger"
                          >
                            <ShieldCheck size={16} />
                            <span>Resolve Emergency</span>
                          </button>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="glass-card nominal-state-large">
                      <ShieldCheck size={48} className="text-success" />
                      <h3>All Monitored Sectors Nominal</h3>
                      <p>No active emergencies, bottleneck crushes, or rapid influx warnings currently detected.</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Notification Dispatch & Email Test Form */}
              <div className="alerts-section">
                <div className="section-title-row">
                  <div className="title-left">
                    <Mail size={20} />
                    <h3>Automated Notification Dispatcher</h3>
                  </div>
                </div>

                <div className="glass-card notification-dispatch-card">
                  <div className="card-desc">
                    CrowdPatrol automatically dispatches Gmail SMTP alert notifications to security officers whenever HIGH or CRITICAL hazards are detected. You can test dispatch delivery below.
                  </div>

                  <form onSubmit={handleSendTestEmail} className="test-email-form">
                    <div className="form-group inline-group">
                      <label htmlFor="testEmail">Recipient Email (Optional override):</label>
                      <div className="input-with-button">
                        <input
                          id="testEmail"
                          type="email"
                          placeholder="Leave blank to use .env ALERT_RECIPIENT_EMAIL"
                          value={testEmailInput}
                          onChange={(e) => setTestEmailInput(e.target.value)}
                          className="form-input"
                        />
                        <button type="submit" className="btn-primary" disabled={actionLoading}>
                          <Send size={16} />
                          <span>Dispatch Test Alert</span>
                        </button>
                      </div>
                    </div>
                  </form>
                </div>
              </div>

              {/* Notifications Log Table */}
              <div className="alerts-section">
                <div className="section-title-row">
                  <div className="title-left">
                    <FileText size={20} />
                    <h3>Notification Dispatch Ledger</h3>
                  </div>
                  <span className="count-pill">{notificationsLog.length} Records</span>
                </div>

                <div className="glass-card table-card">
                  {notificationsLog.length > 0 ? (
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Timestamp</th>
                          <th>Channel</th>
                          <th>Recipient</th>
                          <th>Severity</th>
                          <th>Status</th>
                          <th>Summary</th>
                        </tr>
                      </thead>
                      <tbody>
                        {notificationsLog.map((log, idx) => (
                          <tr key={idx}>
                            <td>{log.timestamp || 'N/A'}</td>
                            <td><span className="badge-id">{log.channel || 'EMAIL'}</span></td>
                            <td>{log.recipient || 'Security Desk'}</td>
                            <td>
                              <span className="severity-pill" style={{ backgroundColor: getRiskColor(log.severity) }}>
                                {log.severity}
                              </span>
                            </td>
                            <td>
                              <span className={`status-tag ${log.status === 'SENT' ? 'tag-success' : 'tag-warning'}`}>
                                {log.status || 'SENT'}
                              </span>
                            </td>
                            <td>{log.subject || log.message || 'Emergency crowd notification'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="empty-table-state">
                      <p>No external notifications logged in this operational session.</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: ANALYTICS */}
          {activeTab === 'analytics' && (
            <div className="tab-pane analytics-pane">
              {/* Real-time Telemetry Metrics */}
              <div className="kpi-grid">
                <div className="glass-card kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-label">Current Person Count</span>
                    <Users size={18} className="text-cyan" />
                  </div>
                  <div className="kpi-value">{analyticsData.current?.person_count || 0}</div>
                  <div className="kpi-meta">Across monitored active feeds</div>
                </div>

                <div className="glass-card kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-label">Peak Density</span>
                    <Flame size={18} className="text-danger" />
                  </div>
                  <div className="kpi-value">
                    {analyticsData.current?.max_density ? analyticsData.current.max_density.toFixed(1) : '0.0'}
                  </div>
                  <div className="kpi-meta">Persons per localized unit</div>
                </div>

                <div className="glass-card kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-label">Average Speed</span>
                    <Activity size={18} className="text-cyan" />
                  </div>
                  <div className="kpi-value">
                    {analyticsData.current?.avg_speed ? `${analyticsData.current.avg_speed.toFixed(1)} px/s` : '0.0 px/s'}
                  </div>
                  <div className="kpi-meta">Optical flow motion vector</div>
                </div>

                <div className="glass-card kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-label">Dominant Direction</span>
                    <Compass size={18} className="text-warning" />
                  </div>
                  <div className="kpi-value">{analyticsData.current?.dominant_direction || 'STATIC'}</div>
                  <div className="kpi-meta">Ego-compensated heading</div>
                </div>
              </div>

              {/* Historical Telemetry Stream Table */}
              <div className="overview-section-box">
                <div className="section-title-row">
                  <div className="title-left">
                    <Activity size={18} />
                    <h3>Historical Telemetry Trend Record</h3>
                  </div>
                  <span className="count-pill">
                    {analyticsData.history?.timestamps?.length || 0} Time-Series Samples
                  </span>
                </div>

                <div className="glass-card table-card">
                  {analyticsData.history?.timestamps && analyticsData.history.timestamps.length > 0 ? (
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Timestamp</th>
                          <th>Person Count</th>
                          <th>Risk Score</th>
                          <th>Max Density</th>
                          <th>Risk Classification</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analyticsData.history.timestamps.slice(-15).reverse().map((ts, idx) => {
                          const originalIdx = analyticsData.history.timestamps.length - 1 - idx;
                          const score = analyticsData.history.risk_scores?.[originalIdx] || 0.0;
                          const count = analyticsData.history.person_counts?.[originalIdx] || 0;
                          const density = analyticsData.history.densities?.[originalIdx] || 0.0;
                          const riskClassification = score >= 75 ? 'Critical' : score >= 50 ? 'High' : score >= 25 ? 'Medium' : 'Low';

                          return (
                            <tr key={idx}>
                              <td>{ts}</td>
                              <td><strong>{count}</strong></td>
                              <td>{score.toFixed(1)} / 100</td>
                              <td>{density.toFixed(1)}</td>
                              <td>
                                <span className="severity-pill" style={{ backgroundColor: getRiskColor(riskClassification) }}>
                                  {riskClassification}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  ) : (
                    <div className="nominal-state">
                      <Clock size={36} className="text-cyan" />
                      <h4>Telemetry Stream Standby</h4>
                      <p>
                        {systemStatus.is_running
                          ? 'Accumulating initial time-series data points from the active AI pipeline...'
                          : 'Click "Start Monitoring" in the header to activate the real-time AI capture loop and generate telemetry.'}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: SETTINGS */}
          {activeTab === 'settings' && (
            <div className="tab-pane settings-pane">
              {/* Vision Inference Configuration */}
              <div className="settings-section">
                <div className="section-title-row">
                  <div className="title-left">
                    <Sliders size={20} />
                    <h3>Vision & Inference Settings</h3>
                  </div>
                </div>

                <div className="glass-card form-card">
                  <form onSubmit={handleSaveConfig} className="settings-form">
                    <div className="form-grid">
                      {/* Detection Mode */}
                      <div className="form-group">
                        <label htmlFor="detectionMode">Detection Model Mode:</label>
                        <select
                          id="detectionMode"
                          value={settingsForm.detection_mode}
                          onChange={(e) => setSettingsForm({ ...settingsForm, detection_mode: e.target.value })}
                          className="form-select"
                        >
                          <option value="PERSON">PERSON MODE (YOLOv8 Standard)</option>
                          <option value="HEAD">HEAD MODE (Overhead & High Density)</option>
                        </select>
                        <span className="field-hint">
                          Head Mode optimizes for top-down crowds where body silhouettes are occluded.
                        </span>
                      </div>

                      {/* Tiled Inference Mode */}
                      <div className="form-group">
                        <label htmlFor="tiledMode">Spatial Tiled Inference:</label>
                        <select
                          id="tiledMode"
                          value={settingsForm.tiled_mode ? 'true' : 'false'}
                          onChange={(e) => setSettingsForm({ ...settingsForm, tiled_mode: e.target.value === 'true' })}
                          className="form-select"
                        >
                          <option value="false">Standard (Single Image)</option>
                          <option value="true">2×2 Batched Spatial Tiling</option>
                        </select>
                        <span className="field-hint">
                          Splits frame into 4 quadrants for detecting distant, small individuals.
                        </span>
                      </div>

                      {/* Confidence Threshold */}
                      <div className="form-group">
                        <label htmlFor="confidenceSlider">
                          Detection Confidence Threshold: <strong>{settingsForm.confidence}</strong>
                        </label>
                        <input
                          id="confidenceSlider"
                          type="range"
                          min="0.10"
                          max="0.90"
                          step="0.05"
                          value={settingsForm.confidence}
                          onChange={(e) => setSettingsForm({ ...settingsForm, confidence: parseFloat(e.target.value) })}
                          className="form-range"
                        />
                        <span className="field-hint">
                          Default is 0.25 for head detection (640×640 resolution).
                        </span>
                      </div>

                      {/* Detection Interval */}
                      <div className="form-group">
                        <label htmlFor="detectInterval">Detection Interval (Frames):</label>
                        <input
                          id="detectInterval"
                          type="number"
                          min="1"
                          max="10"
                          value={settingsForm.detect_interval}
                          onChange={(e) => setSettingsForm({ ...settingsForm, detect_interval: parseInt(e.target.value, 10) || 1 })}
                          className="form-input"
                        />
                        <span className="field-hint">
                          Interval between neural detections (DeepSORT tracks between intervals).
                        </span>
                      </div>
                    </div>

                    <div className="form-actions">
                      <button type="submit" className="btn-primary" disabled={actionLoading}>
                        <CheckCircle2 size={16} />
                        <span>Apply & Save Configuration</span>
                      </button>
                    </div>
                  </form>
                </div>
              </div>

              {/* Configured Camera Feeds & Source Switching */}
              <div className="settings-section">
                <div className="section-title-row">
                  <div className="title-left">
                    <Video size={20} />
                    <h3>Configured Camera Feeds & Live Source Management</h3>
                  </div>
                  <button
                    onClick={() => {
                      const nextId = `CAM-0${(camerasData.configured_cameras?.length || 0) + 1}`;
                      setEditingCameraId(nextId);
                      setCameraForm({
                        id: nextId,
                        name: `Sector ${nextId}`,
                        source: '0',
                        source_type: 'webcam',
                        enabled: true
                      });
                    }}
                    className="btn-secondary btn-sm"
                  >
                    + Add Camera Feed
                  </button>
                </div>

                {editingCameraId && (
                  <div className="glass-card form-card mb-4" style={{ marginBottom: '18px', border: '1px solid var(--accent-cyan)' }}>
                    <h4>Configure Camera Feed: <strong>{editingCameraId}</strong></h4>
                    <form onSubmit={handleSaveCamera} className="camera-edit-form">
                      <div className="form-grid">
                        <div className="form-group">
                          <label>Camera ID:</label>
                          <input type="text" value={cameraForm.id} readOnly className="form-input" style={{ opacity: 0.7 }} />
                        </div>
                        <div className="form-group">
                          <label>Display Name:</label>
                          <input
                            type="text"
                            value={cameraForm.name}
                            onChange={(e) => setCameraForm({ ...cameraForm, name: e.target.value })}
                            className="form-input"
                            required
                          />
                        </div>
                        <div className="form-group">
                          <label>Source Type:</label>
                          <select
                            value={cameraForm.source_type}
                            onChange={(e) => setCameraForm({ ...cameraForm, source_type: e.target.value })}
                            className="form-select"
                          >
                            <option value="video">Recorded Video File</option>
                            <option value="webcam">Physical / USB Webcam (Index)</option>
                            <option value="rtsp">Network RTSP Stream</option>
                            <option value="phone">Mobile Phone Camera (IP Webcam / MJPEG)</option>
                          </select>
                        </div>
                        <div className="form-group">
                          <label>Source Path / Index / URL:</label>
                          <input
                            type="text"
                            value={cameraForm.source}
                            onChange={(e) => setCameraForm({ ...cameraForm, source: e.target.value })}
                            placeholder={cameraForm.source_type === 'webcam' ? 'Device index (e.g. 0 or 1)' : cameraForm.source_type === 'video' ? 'Path to .mp4' : 'rtsp://... or http://...'}
                            className="form-input"
                            required
                          />
                        </div>
                      </div>
                      <div className="form-group" style={{ flexDirection: 'row', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                        <input
                          type="checkbox"
                          id="camEnabledCheck"
                          checked={cameraForm.enabled}
                          onChange={(e) => setCameraForm({ ...cameraForm, enabled: e.target.checked })}
                        />
                        <label htmlFor="camEnabledCheck">Enable this camera in CCTV surveillance loop</label>
                      </div>
                      <div className="form-actions" style={{ gap: '10px' }}>
                        <button type="button" onClick={() => setEditingCameraId(null)} className="btn-secondary">
                          Cancel
                        </button>
                        <button type="submit" className="btn-primary" disabled={actionLoading}>
                          Save & Apply Camera Feed
                        </button>
                      </div>
                    </form>
                  </div>
                )}

                <div className="glass-card table-card">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Source Type</th>
                        <th>Source Target</th>
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {camerasData.configured_cameras && camerasData.configured_cameras.map((cam) => (
                        <tr key={cam.id}>
                          <td><span className="badge-id">{cam.id}</span></td>
                          <td><strong>{cam.name || cam.id}</strong></td>
                          <td><span className="source-type-badge">{cam.source_type?.toUpperCase() || 'VIDEO'}</span></td>
                          <td style={{ maxWidth: '200px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {String(cam.source)}
                          </td>
                          <td>
                            <span className={`channel-status-pill ${cam.enabled ? 'status-enabled' : 'status-disabled'}`}>
                              {cam.enabled ? 'Enabled' : 'Disabled'}
                            </span>
                          </td>
                          <td>
                            <div className="table-actions">
                              <button onClick={() => handleEditCamera(cam)} className="btn-secondary btn-xs">
                                Edit Source
                              </button>
                              <button onClick={() => handleDeleteCamera(cam.id)} className="btn-danger btn-xs">
                                Remove
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Hardware Device Discovery & Camera Test */}
              <div className="settings-section">
                <div className="section-title-row">
                  <div className="title-left">
                    <HardDrive size={20} />
                    <h3>Hardware Camera Diagnostics & Discovery</h3>
                  </div>
                </div>

                <div className="glass-card hardware-card">
                  <div className="discovered-block">
                    <h4>Discovered System Hardware:</h4>
                    {camerasData.discovered_devices && camerasData.discovered_devices.length > 0 ? (
                      <div className="discovered-tags">
                        {camerasData.discovered_devices.map((dev, idx) => (
                          <span key={idx} className="dev-tag">
                            <Camera size={14} />
                            <span>{dev.name || `Device Index ${dev.index}`}</span>
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="subtext">No physical USB webcams detected by hardware scanner.</p>
                    )}
                  </div>

                  {/* Test Camera Form */}
                  <form onSubmit={handleTestCamera} className="test-camera-form">
                    <h4>Test Camera Source Connection:</h4>
                    <div className="input-with-button">
                      <input
                        type="text"
                        placeholder="Device index (e.g. 0), RTSP URL, or video path"
                        value={testCameraSourceInput}
                        onChange={(e) => setTestCameraSourceInput(e.target.value)}
                        className="form-input"
                      />
                      <button type="submit" className="btn-secondary" disabled={actionLoading}>
                        Test Source
                      </button>
                    </div>
                    {testCameraResult && (
                      <div className={`test-result-box ${testCameraResult.success ? 'res-success' : 'res-fail'}`}>
                        {testCameraResult.success ? (
                          <span>✓ Camera accessible! Resolution: {testCameraResult.resolution || 'Verified'}</span>
                        ) : (
                          <span>✕ Error: {testCameraResult.message || 'Cannot open camera stream'}</span>
                        )}
                      </div>
                    )}
                  </form>

                  {/* Phone URL Helper */}
                  <div className="phone-url-helper">
                    <h4>Mobile Phone Camera Stream Generator:</h4>
                    <p className="subtext">
                      Easily generate RTSP / MJPEG URLs for IP Webcam (Android) or Windows Phone streaming:
                    </p>
                    <div className="phone-grid">
                      <input
                        type="text"
                        placeholder="Phone IP (e.g. 192.168.1.100)"
                        value={phoneIp}
                        onChange={(e) => setPhoneIp(e.target.value)}
                        className="form-input"
                      />
                      <input
                        type="number"
                        placeholder="Port (8080)"
                        value={phonePort}
                        onChange={(e) => setPhonePort(parseInt(e.target.value, 10) || 8080)}
                        className="form-input"
                      />
                      <button type="button" onClick={handleGeneratePhoneUrl} className="btn-secondary">
                        Generate URL
                      </button>
                    </div>
                    {generatedPhoneUrl && (
                      <div className="generated-url-box">
                        <code>{generatedPhoneUrl}</code>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Embedded CSS for Dark CCTV Command Center */}
      <style>{`
        .dashboard-container {
          min-height: 100vh;
          background-color: #070a11;
          color: var(--text-primary);
          display: flex;
          flex-direction: column;
        }

        /* Top Header */
        .dashboard-header {
          padding: 14px 24px;
          border-bottom: 1px solid var(--border-color);
          display: flex;
          justify-content: space-between;
          align-items: center;
          position: sticky;
          top: 0;
          z-index: 100;
          background: rgba(10, 14, 23, 0.94);
          backdrop-filter: blur(12px);
        }
        .header-left {
          display: flex;
          align-items: center;
          gap: 16px;
        }
        .return-btn {
          padding: 6px 12px;
          font-size: 0.85rem;
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }
        .header-divider {
          width: 1px;
          height: 28px;
          background: var(--border-color);
        }
        .header-branding {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        .system-status-indicator {
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }
        .status-text {
          font-size: 0.72rem;
          font-weight: 700;
          letter-spacing: 0.08em;
          color: var(--text-muted);
        }
        .header-title {
          font-size: 1.15rem;
          font-weight: 700;
          margin: 0;
          letter-spacing: -0.01em;
        }

        .header-right {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .header-badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 6px 12px;
          border-radius: 6px;
          font-size: 0.78rem;
          font-weight: 600;
          background: rgba(255, 255, 255, 0.04);
          border: 1px solid var(--border-color);
        }
        .mode-badge {
          color: var(--accent-cyan);
        }
        .firebase-badge {
          color: var(--text-secondary);
        }
        .btn-icon {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid var(--border-color);
          color: var(--text-primary);
          padding: 8px;
          border-radius: 6px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .btn-icon:hover {
          background: rgba(255, 255, 255, 0.1);
        }
        .spinning {
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        /* Notice Banners */
        .notice-banner {
          padding: 12px 24px;
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 0.88rem;
        }
        .notice-success {
          background: rgba(16, 185, 129, 0.15);
          border-bottom: 1px solid rgba(16, 185, 129, 0.3);
          color: #a7f3d0;
        }
        .notice-error {
          background: rgba(239, 68, 68, 0.15);
          border-bottom: 1px solid rgba(239, 68, 68, 0.3);
          color: #fca5a5;
        }
        .notice-content {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .notice-close {
          background: transparent;
          border: none;
          color: inherit;
          cursor: pointer;
          font-size: 1rem;
        }

        /* Dashboard Layout */
        .dashboard-body {
          flex: 1;
          display: flex;
        }

        /* Sidebar */
        .dashboard-sidebar {
          width: 250px;
          border-right: 1px solid var(--border-color);
          border-radius: 0;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 16px 12px;
          background: rgba(10, 14, 23, 0.6);
        }
        .sidebar-nav {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .sidebar-tab {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 10px 14px;
          border-radius: 8px;
          background: transparent;
          border: none;
          color: var(--text-secondary);
          font-size: 0.92rem;
          font-weight: 500;
          cursor: pointer;
          text-align: left;
          transition: var(--transition-fast);
          position: relative;
        }
        .sidebar-tab:hover {
          color: var(--text-primary);
          background: rgba(255, 255, 255, 0.05);
        }
        .sidebar-tab.active {
          color: var(--accent-cyan);
          background: rgba(0, 210, 255, 0.1);
          font-weight: 600;
        }
        .sidebar-alert-badge {
          margin-left: auto;
          background: var(--danger);
          color: white;
          font-size: 0.72rem;
          font-weight: 700;
          padding: 2px 7px;
          border-radius: 10px;
        }
        .sidebar-footer {
          margin-top: 24px;
        }
        .sidebar-info-box {
          background: rgba(0, 0, 0, 0.3);
          border: 1px solid var(--border-color);
          border-radius: 8px;
          padding: 12px;
          font-size: 0.78rem;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .info-row {
          display: flex;
          justify-content: space-between;
        }
        .info-key {
          color: var(--text-muted);
        }
        .info-val {
          color: var(--text-primary);
          font-weight: 600;
        }

        /* Content Area */
        .dashboard-content {
          flex: 1;
          padding: 24px 32px;
          overflow-y: auto;
        }

        /* KPI Cards Grid */
        .kpi-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 18px;
          margin-bottom: 24px;
        }
        .kpi-card {
          padding: 20px;
          border: 1px solid var(--border-color);
        }
        .kpi-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }
        .kpi-label {
          font-size: 0.8rem;
          font-weight: 600;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .kpi-value {
          font-size: 2rem;
          font-weight: 800;
          letter-spacing: -0.02em;
          margin-bottom: 8px;
        }
        .kpi-meta {
          font-size: 0.8rem;
          color: var(--text-secondary);
        }

        /* Section Rows */
        .overview-section-box, .alerts-section, .settings-section {
          margin-bottom: 28px;
        }
        .section-title-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 14px;
        }
        .title-left {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .title-left h3 {
          font-size: 1.15rem;
          font-weight: 700;
          margin: 0;
        }
        .count-pill {
          font-size: 0.78rem;
          color: var(--text-muted);
          background: rgba(255, 255, 255, 0.05);
          padding: 4px 10px;
          border-radius: 12px;
          border: 1px solid var(--border-color);
        }
        .btn-link {
          background: transparent;
          border: none;
          color: var(--accent-cyan);
          cursor: pointer;
          font-size: 0.88rem;
          font-weight: 600;
        }

        /* Channel Cards */
        .cam-channels-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
          gap: 16px;
        }
        .channel-card {
          padding: 16px;
          border: 1px solid var(--border-color);
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        .channel-focused {
          border-color: var(--accent-cyan);
          box-shadow: 0 0 15px rgba(0, 210, 255, 0.15);
        }
        .channel-top {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .channel-name {
          font-weight: 700;
          font-size: 0.95rem;
        }
        .channel-status-pill {
          font-size: 0.72rem;
          font-weight: 600;
          padding: 2px 8px;
          border-radius: 4px;
        }
        .status-enabled {
          background: rgba(16, 185, 129, 0.15);
          color: var(--success);
        }
        .status-disabled {
          background: rgba(239, 68, 68, 0.15);
          color: var(--danger);
        }
        .channel-id-row {
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .badge-id {
          font-size: 0.75rem;
          font-weight: 700;
          background: rgba(255, 255, 255, 0.08);
          padding: 2px 6px;
          border-radius: 4px;
        }
        .badge-focus {
          font-size: 0.7rem;
          font-weight: 700;
          background: rgba(0, 210, 255, 0.2);
          color: var(--accent-cyan);
          padding: 2px 6px;
          border-radius: 4px;
        }
        .channel-meta-box {
          font-size: 0.8rem;
          color: var(--text-secondary);
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .meta-line {
          display: flex;
          justify-content: space-between;
        }
        .meta-val {
          color: var(--text-primary);
          max-width: 140px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .channel-footer {
          margin-top: auto;
          padding-top: 8px;
        }
        .btn-focused {
          background: rgba(0, 210, 255, 0.15) !important;
          color: var(--accent-cyan) !important;
          border-color: var(--accent-cyan) !important;
        }

        /* CCTV Grid in Tab 2 */
        .cctv-2x2-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 16px;
        }
        .cctv-cam-slot {
          padding: 14px;
          border: 1px solid var(--border-color);
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        .slot-focus {
          border-color: var(--accent-cyan);
        }
        .slot-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .slot-title-group {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .live-dot-pulse {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--danger);
          box-shadow: 0 0 8px var(--danger);
        }
        .slot-cam-name {
          font-size: 0.95rem;
          font-weight: 700;
        }
        .slot-badges {
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .focus-badge {
          font-size: 0.7rem;
          font-weight: 700;
          color: var(--accent-cyan);
          background: rgba(0, 210, 255, 0.15);
          padding: 2px 6px;
          border-radius: 4px;
        }
        .id-badge {
          font-size: 0.75rem;
          font-weight: 700;
          background: rgba(255, 255, 255, 0.08);
          padding: 2px 6px;
          border-radius: 4px;
        }
        .slot-viewport {
          background: #020408;
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 6px;
          aspect-ratio: 16 / 9;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 10px;
          position: relative;
        }
        .viewport-overlay-top, .viewport-overlay-bottom {
          display: flex;
          justify-content: space-between;
          font-size: 0.72rem;
          color: var(--text-muted);
          font-family: monospace;
          z-index: 2;
        }
        .viewport-center-graphic {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 6px;
          color: var(--text-muted);
        }
        .cam-center-icon {
          color: var(--border-color);
        }
        .viewport-status-text {
          font-size: 0.88rem;
          font-weight: 600;
          color: var(--text-secondary);
        }
        .viewport-subtext {
          font-size: 0.75rem;
          color: var(--text-muted);
        }
        .slot-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 0.8rem;
        }
        .slot-meta-info {
          display: flex;
          gap: 12px;
          color: var(--text-secondary);
        }

        /* Tables */
        .table-card {
          padding: 0;
          overflow-x: auto;
          border: 1px solid var(--border-color);
        }
        .data-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 0.88rem;
          text-align: left;
        }
        .data-table th {
          background: rgba(255, 255, 255, 0.02);
          padding: 12px 16px;
          color: var(--text-muted);
          font-weight: 600;
          border-bottom: 1px solid var(--border-color);
        }
        .data-table td {
          padding: 12px 16px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        }
        .alert-row-active {
          background: rgba(239, 68, 68, 0.05);
        }
        .severity-pill {
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 0.72rem;
          font-weight: 700;
          color: white;
        }
        .status-tag {
          font-size: 0.78rem;
          color: var(--text-secondary);
        }
        .tag-success {
          color: var(--success);
        }
        .tag-warning {
          color: var(--warning);
        }
        .table-actions {
          display: flex;
          gap: 6px;
        }
        .btn-xs {
          padding: 4px 8px;
          font-size: 0.75rem;
        }

        /* Nominal Empty States */
        .nominal-state {
          padding: 36px 20px;
          text-align: center;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 10px;
        }
        .nominal-state h4, .nominal-state-large h3 {
          margin: 0;
        }
        .nominal-state p, .nominal-state-large p {
          color: var(--text-secondary);
          max-width: 500px;
          margin: 0;
          font-size: 0.9rem;
        }
        .nominal-state-large {
          padding: 48px 24px;
          text-align: center;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
          border: 1px solid var(--border-color);
        }

        /* Active Alerts List */
        .active-alerts-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .active-alert-card {
          padding: 16px 20px;
          border: 1px solid rgba(239, 68, 68, 0.4);
          display: flex;
          justify-content: space-between;
          align-items: center;
          background: rgba(239, 68, 68, 0.06);
        }
        .alert-card-left {
          display: flex;
          align-items: center;
          gap: 16px;
        }
        .severity-indicator {
          width: 6px;
          height: 48px;
          border-radius: 3px;
        }
        .alert-card-info {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .alert-card-header {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .alert-cam-pill {
          background: rgba(255, 255, 255, 0.1);
          font-weight: 700;
          font-size: 0.75rem;
          padding: 2px 6px;
          border-radius: 4px;
        }
        .severity-badge {
          color: white;
          font-weight: 700;
          font-size: 0.72rem;
          padding: 2px 6px;
          border-radius: 4px;
        }
        .alert-timestamp {
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 0.75rem;
          color: var(--text-muted);
        }
        .alert-reason-title {
          margin: 0;
          font-size: 1rem;
          font-weight: 700;
        }
        .alert-details-row {
          font-size: 0.8rem;
          color: var(--text-secondary);
          display: flex;
          gap: 16px;
        }
        .alert-card-actions {
          display: flex;
          gap: 10px;
        }

        /* Settings & Forms */
        .form-card, .hardware-card, .notification-dispatch-card {
          padding: 24px;
          border: 1px solid var(--border-color);
        }
        .form-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 20px;
          margin-bottom: 24px;
        }
        .form-group {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .form-group label {
          font-size: 0.88rem;
          font-weight: 600;
          color: var(--text-secondary);
        }
        .form-input, .form-select {
          background: rgba(0, 0, 0, 0.4);
          border: 1px solid var(--border-color);
          border-radius: 6px;
          padding: 10px 14px;
          color: var(--text-primary);
          font-size: 0.9rem;
        }
        .form-input:focus, .form-select:focus {
          outline: none;
          border-color: var(--accent-cyan);
        }
        .form-range {
          accent-color: var(--accent-cyan);
        }
        .field-hint {
          font-size: 0.75rem;
          color: var(--text-muted);
        }
        .form-actions {
          display: flex;
          justify-content: flex-end;
        }
        .inline-group {
          max-width: 650px;
        }
        .input-with-button {
          display: flex;
          gap: 10px;
        }
        .input-with-button .form-input {
          flex: 1;
        }
        .card-desc {
          font-size: 0.88rem;
          color: var(--text-secondary);
          margin-bottom: 16px;
          max-width: 700px;
        }

        /* Hardware diagnostics */
        .discovered-block {
          margin-bottom: 24px;
        }
        .discovered-block h4, .test-camera-form h4, .phone-url-helper h4 {
          margin: 0 0 8px 0;
          font-size: 0.95rem;
        }
        .discovered-tags {
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
        }
        .dev-tag {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          background: rgba(0, 210, 255, 0.1);
          border: 1px solid rgba(0, 210, 255, 0.3);
          color: var(--accent-cyan);
          padding: 4px 10px;
          border-radius: 6px;
          font-size: 0.85rem;
        }
        .subtext {
          font-size: 0.82rem;
          color: var(--text-muted);
          margin-bottom: 10px;
        }
        .test-camera-form {
          margin-bottom: 24px;
          max-width: 650px;
        }
        .test-result-box {
          margin-top: 8px;
          padding: 8px 12px;
          border-radius: 6px;
          font-size: 0.85rem;
        }
        .res-success {
          background: rgba(16, 185, 129, 0.15);
          color: var(--success);
        }
        .res-fail {
          background: rgba(239, 68, 68, 0.15);
          color: var(--danger);
        }
        .phone-url-helper {
          max-width: 650px;
        }
        .phone-grid {
          display: grid;
          grid-template-columns: 2fr 1fr auto;
          gap: 10px;
          margin-bottom: 8px;
        }
        .generated-url-box {
          background: #020408;
          border: 1px solid var(--border-color);
          padding: 8px 12px;
          border-radius: 6px;
          font-size: 0.85rem;
          color: var(--accent-cyan);
        }

        /* Utilities */
        .text-cyan { color: var(--accent-cyan); }
        .text-success { color: var(--success); }
        .text-danger { color: var(--danger); }
        .text-warning { color: var(--warning); }
        .btn-sm {
          padding: 6px 12px;
          font-size: 0.8rem;
        }

        /* Responsive Breakpoints */
        @media (max-width: 900px) {
          .dashboard-body {
            flex-direction: column;
          }
          .dashboard-sidebar {
            width: 100%;
            border-right: none;
            border-bottom: 1px solid var(--border-color);
          }
          .sidebar-nav {
            flex-direction: row;
            flex-wrap: wrap;
          }
          .cctv-2x2-grid {
            grid-template-columns: 1fr;
          }
        }

        /* Surveillance Toolbar */
        .stream-toolbar {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 12px;
          margin-bottom: 20px;
          padding: 10px 18px;
          border: 1px solid var(--border-color);
        }
        .toolbar-left, .toolbar-center, .toolbar-right {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .toolbar-label {
          font-size: 0.72rem;
          font-weight: 700;
          color: var(--text-muted);
          letter-spacing: 0.08em;
        }
        .layout-btn-group, .cam-pill-group {
          display: flex;
          gap: 6px;
        }
        .btn-toolbar {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 6px 12px;
          border-radius: 6px;
          font-size: 0.82rem;
          font-weight: 600;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid var(--border-color);
          color: var(--text-secondary);
          cursor: pointer;
          transition: var(--transition-fast);
        }
        .btn-toolbar:hover {
          color: var(--text-primary);
          background: rgba(255, 255, 255, 0.09);
        }
        .btn-toolbar.active {
          color: var(--accent-cyan);
          background: rgba(0, 210, 255, 0.15);
          border-color: var(--accent-cyan);
        }
        .btn-toolbar.active-heatmap {
          color: #f97316;
          background: rgba(249, 115, 22, 0.15);
          border-color: #f97316;
        }
        .btn-cam-pill {
          padding: 5px 10px;
          border-radius: 5px;
          font-size: 0.78rem;
          font-weight: 700;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid var(--border-color);
          color: var(--text-secondary);
          cursor: pointer;
          transition: var(--transition-fast);
        }
        .btn-cam-pill:hover {
          color: var(--text-primary);
          background: rgba(255, 255, 255, 0.1);
        }
        .btn-cam-pill.active-focus {
          color: var(--accent-cyan);
          background: rgba(0, 210, 255, 0.2);
          border-color: var(--accent-cyan);
        }

        /* Live Video Streaming Elements */
        .cctv-live-img {
          width: 100%;
          height: 100%;
          object-fit: contain;
          background: #020408;
          border-radius: 4px;
          display: block;
        }
        .live-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          display: inline-block;
        }
        .dot-pulse-live {
          background: var(--danger);
          box-shadow: 0 0 8px var(--danger);
          animation: pulseDot 1.5s infinite;
        }
        .dot-standby {
          background: var(--accent-cyan);
        }
        @keyframes pulseDot {
          0% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.9); }
          100% { opacity: 1; transform: scale(1); }
        }
        .source-type-badge {
          font-size: 0.68rem;
          font-weight: 700;
          color: var(--text-muted);
          background: rgba(255, 255, 255, 0.05);
          padding: 2px 5px;
          border-radius: 3px;
        }

        /* Standby & Error Overlays */
        .stream-standby-overlay {
          position: absolute;
          inset: 0;
          background: rgba(7, 10, 17, 0.9);
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 6px;
          z-index: 5;
          text-align: center;
          padding: 16px;
        }
        .large-overlay {
          gap: 12px;
        }
        .standby-title {
          font-size: 0.95rem;
          font-weight: 700;
          color: var(--text-primary);
        }
        .standby-desc {
          font-size: 0.78rem;
          color: var(--text-muted);
          margin-bottom: 6px;
          max-width: 380px;
        }

        /* Focus Feed Layout */
        .cctv-focus-container, .cctv-composite-container {
          display: flex;
          flex-direction: column;
          gap: 18px;
        }
        .focus-stream-card, .composite-card {
          padding: 20px;
          border: 1px solid var(--border-color);
        }
        .focus-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 14px;
        }
        .focus-title-group {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .focus-title-group h3 {
          margin: 0;
          font-size: 1.15rem;
        }
        .heatmap-active-pill {
          margin-left: 12px;
          font-size: 0.72rem;
          font-weight: 700;
          color: #f97316;
          background: rgba(249, 115, 22, 0.15);
          padding: 3px 8px;
          border-radius: 4px;
          border: 1px solid rgba(249, 115, 22, 0.3);
        }
        .focus-viewport, .composite-viewport {
          background: #000;
          border-radius: 6px;
          aspect-ratio: 16 / 9;
          max-height: 640px;
          overflow: hidden;
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          border: 1px solid rgba(255, 255, 255, 0.08);
        }
        .overlay-tag-large {
          background: rgba(0, 0, 0, 0.6);
          padding: 4px 10px;
          border-radius: 4px;
          border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .focus-telemetry-hud {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
          gap: 12px;
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid var(--border-color);
        }
        .hud-metric {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .hud-label {
          font-size: 0.72rem;
          font-weight: 600;
          color: var(--text-muted);
          text-transform: uppercase;
        }
        .hud-value {
          font-size: 1.25rem;
          font-weight: 800;
        }
        .slot-btn-actions {
          display: flex;
          gap: 6px;
        }
      `}</style>
    </div>
  );
}

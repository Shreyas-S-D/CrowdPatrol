/**
 * CrowdPatrol Frontend — FastAPI Backend Client
 * Connects React directly to the real Python FastAPI REST endpoints.
 * Handles timeouts, network errors, and offline states cleanly.
 */

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const defaultHeaders = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), options.timeout || 6000);

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        ...defaultHeaders,
        ...(options.headers || {}),
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorText = await response.text();
      let errorJson;
      try {
        errorJson = JSON.parse(errorText);
      } catch {
        errorJson = { message: errorText || `HTTP ${response.status}` };
      }
      throw new Error(errorJson.message || errorJson.detail || `HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new Error('Request timed out connecting to CrowdPatrol AI backend.');
    }
    throw error;
  }
}

// REST Endpoints
export const api = {
  // System Status & Health
  getStatus: () => request('/api/status'),
  getHealth: () => request('/health'),

  // Vision & Inference Configuration
  getConfig: () => request('/api/config'),
  updateConfig: (data) => request('/api/config', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Camera Management & Discovered Hardware
  getCameras: () => request('/api/cameras'),
  setFocusCamera: (cameraId) => request('/api/cameras/focus', {
    method: 'POST',
    body: JSON.stringify({ camera_id: cameraId }),
  }),
  setCameraLayout: (layout, focusCamera = null) => request('/api/cameras/layout', {
    method: 'POST',
    body: JSON.stringify({ layout, focus_camera: focusCamera }),
  }),
  testCameraSource: (source) => request('/api/cameras/test', {
    method: 'POST',
    body: JSON.stringify({ source }),
  }),
  reconfigureCamera: (cameraData) => request('/api/cameras/reconfigure', {
    method: 'POST',
    body: JSON.stringify(cameraData),
  }),
  deleteCamera: (cameraId) => request(`/api/cameras/${cameraId}`, {
    method: 'DELETE',
  }),

  // Telemetry Analytics & Historical Queues
  getAnalyticsSummary: () => request('/api/analytics/summary'),

  // Alert Lifecycle
  getAlerts: (limit = 50) => request(`/api/alerts?limit=${limit}`),
  acknowledgeAlert: (cameraId, operatorId = 'WebOperator') => request(`/api/alerts/${cameraId}/acknowledge`, {
    method: 'POST',
    body: JSON.stringify({ operator_id: operatorId }),
  }),
  resolveAlert: (cameraId, operatorId = 'WebOperator', note = 'Resolved via Web Dashboard') => request(`/api/alerts/${cameraId}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ operator_id: operatorId, note }),
  }),

  // Notifications Log
  getNotificationLog: (limit = 50) => request(`/api/notifications/log?limit=${limit}`),
  sendTestEmail: (toEmail = null) => request('/api/notifications/test-email', {
    method: 'POST',
    body: JSON.stringify({ to_email: toEmail }),
  }),

  // Pipeline Execution Control
  startMonitoring: () => request('/api/monitoring/start', { method: 'POST' }),
  stopMonitoring: () => request('/api/monitoring/stop', { method: 'POST' }),

  // Stream URL Generators
  getLiveStreamUrl: (layout = null, nonce = null) => {
    const params = new URLSearchParams();
    if (layout) params.set('layout', layout);
    if (nonce) params.set('_t', nonce);
    const qs = params.toString();
    return `${API_BASE_URL}/api/stream/live${qs ? `?${qs}` : ''}`;
  },
  getCameraStreamUrl: (cameraId, nonce = null) => {
    return `${API_BASE_URL}/api/stream/camera/${cameraId}${nonce ? `?_t=${nonce}` : ''}`;
  },
  getHeatmapStreamUrl: (nonce = null) => {
    return `${API_BASE_URL}/api/stream/heatmap${nonce ? `?_t=${nonce}` : ''}`;
  },
};

export default api;

"""
Firebase-based alert and notification system for CrowdPatrol.
Replaces Twilio SMS + SMTP email with Firebase Realtime DB + FCM.
"""

import firebase_admin
from firebase_admin import credentials, db, firestore, messaging
from datetime import datetime, timedelta
import json
import os
from pathlib import Path


class FirebaseAlertManager:
    """
    Manages alerts and notifications using Firebase.
    - Stores alerts in Realtime Database
    - Stores historical metrics in Firestore
    - Sends push notifications via FCM
    """
    
    def __init__(
        self,
        credentials_path="firebase-credentials.json",
        database_url=None,
        cooldown=60,
        notification_cooldown=30
    ):
        """
        Initialize Firebase connection.
        
        Args:
            credentials_path: Path to Firebase service account JSON
            database_url: Realtime Database URL
            cooldown: Seconds between storing alerts
            notification_cooldown: Seconds between push notifications
        """
        self.cooldown = cooldown
        self.notification_cooldown = notification_cooldown
        self.last_alert_time = None
        self.last_notification_time = None
        self.alert_counter = 0
        
        # Initialize Firebase
        self._init_firebase(credentials_path, database_url)
        
        print("[✓] Firebase alert system initialized")
    
    def _init_firebase(self, credentials_path, database_url):
        try:
            firebase_admin.get_app()
            print("[*] Firebase already initialized")
        except ValueError:
            if not os.path.exists(credentials_path):
                alt_paths = [
                    Path(__file__).parent.parent / "firebase-credentials.json",
                    Path.home() / ".firebase" / "credentials.json"
                ]
                for path in alt_paths:
                    if path.exists():
                        credentials_path = str(path)
                        break
                else:
                    raise FileNotFoundError(
                        f"Firebase credentials not found at {credentials_path}"
                    )
            
            cred = credentials.Certificate(credentials_path)
            
            # If database_url is NOT provided, get it from config
            if database_url is None:
                try:
                    from config import FIREBASE_DATABASE_URL
                    database_url = FIREBASE_DATABASE_URL
                except ImportError:
                    # Auto-detect from credentials
                    with open(credentials_path, 'r') as f:
                        cred_data = json.load(f)
                        project_id = cred_data.get('project_id')
                        # Default to US region
                        database_url = f"https://{project_id}-default-rtdb.firebaseio.com"
            
            print(f"[*] Connecting to: {database_url}")
            
            firebase_admin.initialize_app(cred, {
                'databaseURL': database_url
            })
            
            print(f"[✓] Firebase connected: {database_url}")
        
        self.rtdb = db
        self.firestore_db = firestore.client()
    
    def can_send_alert(self):
        """Check cooldown for alert storage"""
        if self.last_alert_time is None:
            return True
        return (datetime.now() - self.last_alert_time).total_seconds() > self.cooldown
    
    def can_send_notification(self):
        """Check cooldown for push notifications"""
        if self.last_notification_time is None:
            return True
        return (datetime.now() - self.last_notification_time).total_seconds() > self.notification_cooldown
    
    def store_alert(self, risk_level, density, anomaly_score, person_count, combined_score, growth_rate=0.0, data_quality_score=1.0):
        if not self.can_send_alert():
            return None
        
        timestamp = datetime.now()
        self.alert_counter += 1
        
        alert_data = {
            "alert_id": f"alert_{self.alert_counter:06d}",
            "timestamp": timestamp.isoformat(),
            "timestamp_unix": int(timestamp.timestamp()),
            "risk_level": str(risk_level),
            "density": int(density),                          # ← int()
            "anomaly_score": float(round(anomaly_score, 3)),  # ← float()
            "person_count": int(person_count),                 # ← int()
            "combined_score": float(round(combined_score, 1)), # ← float()
            "growth_rate": float(round(growth_rate, 2)),
            "data_quality_score": float(round(data_quality_score, 2)),
            "acknowledged": False,
            "acknowledged_by": None,
            "acknowledged_at": None
        }
        
        try:
            alerts_ref = self.rtdb.reference('alerts')
            new_alert_ref = alerts_ref.push(alert_data)
            
            status_ref = self.rtdb.reference('current_status')
            status_ref.update({
                "risk_level": str(risk_level),
                "person_count": int(person_count),
                "max_density": int(density),
                "last_updated": timestamp.isoformat(),
                "last_alert_id": new_alert_ref.key
            })
            
            self.last_alert_time = timestamp
            print(f"[✓] Alert stored in Firebase: {risk_level} (ID: {new_alert_ref.key})")
            return new_alert_ref.key
            
        except Exception as e:
            print(f"[!] Failed to store alert: {e}")
            return None
    
    def store_metrics_batch(self, metrics_history):
        """
        Store batch metrics in Firestore for historical analysis.
        
        Args:
            metrics_history: List of metric dictionaries
        """
        try:
            batch = self.firestore_db.batch()
            metrics_ref = self.firestore_db.collection('metrics')
            
            for metrics in metrics_history:
                doc_ref = metrics_ref.document()
                batch.set(doc_ref, {
                    **metrics,
                    "uploaded_at": firestore.SERVER_TIMESTAMP
                })
            
            batch.commit()
            print(f"[✓] Stored {len(metrics_history)} metrics in Firestore")
            
        except Exception as e:
            print(f"[!] Failed to store metrics batch: {e}")
    
    def store_single_metric(self, metrics):
        """
        Store single metric entry in Firestore.
        """
        try:
            doc_ref = self.firestore_db.collection('metrics').document()
            doc_ref.set({
                **metrics,
                "timestamp": firestore.SERVER_TIMESTAMP
            })
        except Exception as e:
            print(f"[!] Failed to store metric: {e}")
    
    def send_push_notification(self, risk_level, density, location="Main Area"):
        """
        Send push notification via Firebase Cloud Messaging.
        
        Args:
            risk_level: Risk level string
            density: Current density count
            location: Monitored location name
        """
        if not self.can_send_notification():
            return
        
        # Only notify for Medium and High risks
        if risk_level == "Low":
            return
        
        try:
            # Topic-based notification (all subscribed devices)
            topic = 'crowd_alerts'
            
            # Create notification message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=f"⚠️ {risk_level} Risk Alert!",
                    body=f"Density: {density} persons detected in {location}"
                ),
                data={
                    "risk_level": risk_level,
                    "density": str(density),
                    "location": location,
                    "timestamp": datetime.now().isoformat(),
                    "click_action": "OPEN_DASHBOARD"
                },
                topic=topic
            )
            
            # Send message
            response = messaging.send(message)
            self.last_notification_time = datetime.now()
            
            print(f"[✓] Push notification sent: {response}")
            
        except Exception as e:
            print(f"[!] Failed to send push notification: {e}")
    
    def send_notification_to_device(self, device_token, risk_level, density, combined_score):
        """
        Send push notification to specific device.
        
        Args:
            device_token: FCM device registration token
            risk_level: Risk level
            density: Density count
            combined_score: Risk score
        """
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=f"🚨 CrowdPatrol: {risk_level} Risk",
                    body=f"Score: {combined_score:.0f}/100 | Persons: {density}"
                ),
                data={
                    "risk_level": risk_level,
                    "score": str(combined_score),
                    "density": str(density)
                },
                token=device_token
            )
            
            response = messaging.send(message)
            print(f"[✓] Device notification sent: {response}")
            return response
            
        except messaging.UnregisteredError:
            print("[!] Device token is unregistered")
        except Exception as e:
            print(f"[!] Failed to send device notification: {e}")
        return None
    
    def mark_alert_acknowledged(self, alert_key, acknowledged_by="Admin"):
        """
        Mark an alert as acknowledged in Firebase.
        """
        try:
            alert_ref = self.rtdb.reference(f'alerts/{alert_key}')
            alert_ref.update({
                "acknowledged": True,
                "acknowledged_by": acknowledged_by,
                "acknowledged_at": datetime.now().isoformat()
            })
            print(f"[✓] Alert {alert_key} acknowledged by {acknowledged_by}")
            
        except Exception as e:
            print(f"[!] Failed to acknowledge alert: {e}")
    
    def get_active_alerts(self, limit=50):
        """
        Get recent unacknowledged alerts from Firebase.
        
        Args:
            limit: Maximum number of alerts to fetch
        
        Returns:
            List of alert dictionaries
        """
        try:
            alerts_ref = self.rtdb.reference('alerts')
            # Get alerts ordered by timestamp, unacknowledged first
            alerts = alerts_ref.order_by_child('acknowledged').equal_to(False).limit_to_last(limit).get()
            
            if alerts:
                return [
                    {"key": key, **value}
                    for key, value in alerts.items()
                ]
            return []
            
        except Exception as e:
            print(f"[!] Failed to fetch alerts: {e}")
            return []
    
    def update_dashboard_data(self, metrics):
        try:
            dashboard_ref = self.rtdb.reference('dashboard')
            
            # Force Python native types (not NumPy)
            import numpy as np
            
            def clean_value(v):
                """Convert NumPy types to Python native types"""
                if isinstance(v, (np.integer,)):
                    return int(v)
                elif isinstance(v, (np.floating,)):
                    return float(v)
                elif isinstance(v, np.ndarray):
                    return v.tolist()
                return v
            
            dashboard_data = {
                "person_count": clean_value(metrics.get("person_count", 0)),
                "max_density": clean_value(metrics.get("density", 0)),
                "risk_level": str(metrics.get("risk", "Low")),
                "combined_score": clean_value(metrics.get("combined_score", 0)),
                "anomaly_score": clean_value(metrics.get("anomaly", 0)),
                "growth_rate": clean_value(metrics.get("growth_rate", 0.0)),
                "data_quality_score": clean_value(metrics.get("data_quality_score", 1.0)),
                "raw_score": clean_value(metrics.get("raw_score", 0.0)),
                "smoothed_score": clean_value(metrics.get("smoothed_score", 0.0)),
                "last_frame_time": datetime.now().isoformat(),
                "fps": clean_value(metrics.get("fps", 0))
            }
            
            dashboard_ref.update(dashboard_data)
            
        except Exception as e:
            print(f"[!] Failed to update dashboard: {e}")

    
    def store_event_log(self, event_type, details):
        try:
            events_ref = self.rtdb.reference('events')
            
            # Use clean timestamp as key instead of auto-generated
            event_data = {
                "type": str(event_type),
                "details": str(details),
                "timestamp": datetime.now().isoformat()
            }
            
            events_ref.push(event_data)
            print(f"[✓] Event logged: {event_type}")
        except Exception as e:
            print(f"[!] Failed to log event: {e}")
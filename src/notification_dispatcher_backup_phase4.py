"""
Notification Delivery System for CrowdPatrol Automated Alert Management.

Features:
- Configurable SMTP email delivery with responsive HTML templates.
- Configurable Twilio SMS delivery with concise, high-priority alert formatting.
- Asynchronous, non-blocking queue worker that never delays YOLO/DeepSORT processing.
- Strict deduplication per alert ID with automatic escalation bypass.
- Configurable severity-based routing (MEDIUM -> Dashboard, HIGH -> Email, CRITICAL -> Email + SMS).
- Bounded exponential retries for transient connection errors.
- Secure credential management reading exclusively from environment variables or .env.
- Safe mockable architecture and detailed delivery history tracking.
"""

import os
import re
import smtplib
import socket
import time
import threading
import queue
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Set, Dict, Any, Optional, Tuple, Callable

# Load environment variables from .env if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Check optional twilio package
try:
    from twilio.rest import Client as TwilioRestClient
    from twilio.base.exceptions import TwilioRestException
    TWILIO_AVAILABLE = True
except ImportError:
    TwilioRestClient = None
    TwilioRestException = Exception
    TWILIO_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# ==============================================================================
# Configuration Data Model
# ==============================================================================

@dataclass
class NotificationConfig:
    """Configuration settings for Email and SMS notification delivery."""
    # SMTP Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    email_sender: Optional[str] = None
    email_recipients: List[str] = field(default_factory=list)
    email_severities: Set[str] = field(default_factory=lambda: {"HIGH", "CRITICAL"})

    # Twilio SMS
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_phone_number: Optional[str] = None
    sms_recipients: List[str] = field(default_factory=list)
    sms_severities: Set[str] = field(default_factory=lambda: {"CRITICAL"})

    # Dispatcher tuning
    enabled: bool = True
    max_retries: int = 3
    retry_backoff: float = 1.0
    queue_timeout: float = 0.5

    @property
    def is_email_configured(self) -> bool:
        """Checks whether all necessary SMTP credentials and recipients are present."""
        return bool(
            self.smtp_host
            and self.smtp_port
            and self.smtp_username
            and self.smtp_password
            and self.email_sender
            and self.email_recipients
        )

    @property
    def is_sms_configured(self) -> bool:
        """Checks whether all necessary Twilio credentials and recipients are present."""
        return bool(
            self.twilio_account_sid
            and self.twilio_auth_token
            and self.twilio_phone_number
            and self.sms_recipients
        )

    @classmethod
    def from_env(cls, env_path: Optional[str] = None) -> "NotificationConfig":
        """Builds NotificationConfig by reading environment variables."""
        if env_path and os.path.exists(env_path):
            try:
                from dotenv import load_dotenv
                load_dotenv(env_path, override=True)
            except ImportError:
                pass

        enabled_str = os.getenv("NOTIFICATION_ENABLED", "true").strip().lower()
        enabled = enabled_str in ("1", "true", "yes", "on")

        # SMTP settings
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
        try:
            smtp_port = int(os.getenv("SMTP_PORT", "587").strip())
        except ValueError:
            smtp_port = 587

        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        email_sender = os.getenv("ALERT_EMAIL_SENDER") or smtp_username

        # Parse recipients
        raw_email_recipients = os.getenv("ALERT_EMAIL_RECIPIENTS", "")
        email_recipients = cls._parse_list(raw_email_recipients)

        raw_email_severities = os.getenv("EMAIL_ALERT_SEVERITIES", "HIGH,CRITICAL")
        email_severities = set(cls._parse_list(raw_email_severities, upper=True)) or {"HIGH", "CRITICAL"}

        # Twilio settings
        twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER")

        raw_sms_recipients = os.getenv("ALERT_SMS_RECIPIENTS", "")
        sms_recipients = cls._parse_list(raw_sms_recipients)

        raw_sms_severities = os.getenv("SMS_ALERT_SEVERITIES", "CRITICAL")
        sms_severities = set(cls._parse_list(raw_sms_severities, upper=True)) or {"CRITICAL"}

        try:
            max_retries = int(os.getenv("NOTIFICATION_MAX_RETRIES", "3").strip())
        except ValueError:
            max_retries = 3

        try:
            retry_backoff = float(os.getenv("NOTIFICATION_RETRY_BACKOFF", "1.0").strip())
        except ValueError:
            retry_backoff = 1.0

        return cls(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_username=smtp_username if smtp_username else None,
            smtp_password=smtp_password if smtp_password else None,
            smtp_use_tls=True,
            email_sender=email_sender if email_sender else None,
            email_recipients=email_recipients,
            email_severities=email_severities,
            twilio_account_sid=twilio_account_sid if twilio_account_sid else None,
            twilio_auth_token=twilio_auth_token if twilio_auth_token else None,
            twilio_phone_number=twilio_phone_number if twilio_phone_number else None,
            sms_recipients=sms_recipients,
            sms_severities=sms_severities,
            enabled=enabled,
            max_retries=max_retries,
            retry_backoff=retry_backoff
        )

    @staticmethod
    def _parse_list(val: str, upper: bool = False) -> List[str]:
        """Parses comma, semicolon or newline delimited list of items."""
        if not val:
            return []
        items = re.split(r"[,;\n]+", val)
        clean = [item.strip() for item in items if item.strip()]
        if upper:
            clean = [item.upper() for item in clean]
        return clean

    def to_safe_dict(self) -> Dict[str, Any]:
        """Returns safe summary without exposing sensitive passwords or auth tokens."""
        return {
            "enabled": self.enabled,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_username": self.smtp_username if self.smtp_username else "(not set)",
            "smtp_password_set": bool(self.smtp_password),
            "email_sender": self.email_sender if self.email_sender else "(not set)",
            "email_recipients": self.email_recipients,
            "email_severities": sorted(list(self.email_severities)),
            "is_email_configured": self.is_email_configured,
            "twilio_account_sid": self.twilio_account_sid[:6] + "..." if self.twilio_account_sid and len(self.twilio_account_sid) > 6 else "(not set)",
            "twilio_auth_token_set": bool(self.twilio_auth_token),
            "twilio_phone_number": self.twilio_phone_number if self.twilio_phone_number else "(not set)",
            "sms_recipients": self.sms_recipients,
            "sms_severities": sorted(list(self.sms_severities)),
            "is_sms_configured": self.is_sms_configured,
            "max_retries": self.max_retries
        }


# ==============================================================================
# Notification Delivery History Record
# ==============================================================================

@dataclass
class NotificationRecord:
    """Historical record of an attempted or dispatched notification."""
    record_id: str
    alert_id: str
    camera_id: str
    channel: str              # "EMAIL" or "SMS"
    recipient: str
    severity: str             # "MEDIUM", "HIGH", "CRITICAL"
    timestamp: str
    status: str               # "SENT", "FAILED", "QUEUED", "RETRYING", "SKIPPED"
    attempts: int = 1
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==============================================================================
# Message Formatters
# ==============================================================================

def format_alert_email_html(alert: Any) -> str:
    """Generates an HTML email notification for an alert event."""
    sev = getattr(alert, "severity", getattr(alert, "risk_level", "HIGH")).upper()
    cat = getattr(alert, "category", "CROWD_RISK")
    cam_id = getattr(alert, "camera_id", "UNKNOWN")
    cam_name = getattr(alert, "camera_name", "Monitored Zone")
    alert_id = getattr(alert, "alert_id", "ALT_UNKNOWN")
    score = float(getattr(alert, "risk_score", 0.0))
    density = int(getattr(alert, "crowd_density", getattr(alert, "primary_zone_density", 0)))
    count = int(getattr(alert, "person_count", 0))
    zone = getattr(alert, "primary_risk_zone", "A1")
    zone_desc = getattr(alert, "zone_description", "Monitored Cell")
    reason = getattr(alert, "reason", "Abnormal crowd activity detected.")
    timestamp = str(getattr(alert, "timestamp", datetime.now().isoformat()))[:19].replace("T", " ")

    if sev == "CRITICAL":
        banner_color = "#d90429"
        banner_title = "CRITICAL CROWD EMERGENCY"
        badge_bg = "#ff0055"
    elif sev == "HIGH":
        banner_color = "#e85d04"
        banner_title = "HIGH-RISK SECURITY ALERT"
        badge_bg = "#f48c06"
    else:
        banner_color = "#faa307"
        banner_title = "CROWD RISK ADVISORY"
        badge_bg = "#ffba08"

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>CrowdPatrol Alert Notification</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; background-color: #f4f5f7; margin: 0; padding: 20px; }}
        .card {{ max-width: 620px; margin: 0 auto; background: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 14px rgba(0,0,0,0.12); }}
        .header {{ background-color: {banner_color}; color: #ffffff; padding: 24px 28px; }}
        .header h1 {{ margin: 0; font-size: 22px; letter-spacing: 0.5px; }}
        .header p {{ margin: 6px 0 0 0; opacity: 0.9; font-size: 14px; }}
        .content {{ padding: 26px 28px; color: #2d3748; }}
        .badge {{ display: inline-block; padding: 4px 10px; border-radius: 4px; color: #ffffff; background: {badge_bg}; font-weight: bold; font-size: 12px; margin-right: 8px; }}
        .metric-grid {{ display: table; width: 100%; margin: 20px 0; border-collapse: separate; border-spacing: 10px; }}
        .metric-cell {{ display: table-cell; width: 33%; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; text-align: center; }}
        .metric-val {{ font-size: 22px; font-weight: bold; color: {banner_color}; margin-top: 4px; }}
        .metric-lbl {{ font-size: 12px; color: #718096; text-transform: uppercase; font-weight: 600; }}
        .detail-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        .detail-table td {{ padding: 10px 12px; border-bottom: 1px solid #edf2f7; font-size: 14px; }}
        .detail-table td.label {{ color: #718096; width: 35%; font-weight: 600; }}
        .detail-table td.value {{ color: #1a202c; font-weight: 500; }}
        .reason-box {{ background: #fff5f5; border-left: 4px solid {banner_color}; padding: 14px 16px; border-radius: 4px; margin: 18px 0; font-size: 14px; color: #742a2a; }}
        .footer {{ background: #edf2f7; padding: 16px 28px; text-align: center; font-size: 12px; color: #718096; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <h1>🚨 {banner_title}</h1>
            <p>Automated real-time alert dispatched by CrowdPatrol Surveillance Engine</p>
        </div>
        <div class="content">
            <div>
                <span class="badge">{sev}</span>
                <span style="font-weight: 600; color: #4a5568;">Category: {cat}</span>
                <span style="float: right; color: #718096; font-size: 13px;">{timestamp}</span>
            </div>

            <div class="reason-box">
                <b>Trigger Reason:</b> {reason}
            </div>

            <div class="metric-grid">
                <div class="metric-cell">
                    <div class="metric-lbl">Risk Score</div>
                    <div class="metric-val">{score:.1f}</div>
                </div>
                <div class="metric-cell">
                    <div class="metric-lbl">Peak Density</div>
                    <div class="metric-val">{density} <span style="font-size: 13px; font-weight: normal;">p/cell</span></div>
                </div>
                <div class="metric-cell">
                    <div class="metric-lbl">Head / Person Count</div>
                    <div class="metric-val">{count}</div>
                </div>
            </div>

            <table class="detail-table">
                <tr>
                    <td class="label">Camera ID</td>
                    <td class="value"><b>{cam_id}</b> ({cam_name})</td>
                </tr>
                <tr>
                    <td class="label">Primary Risk Zone</td>
                    <td class="value">Zone <b>{zone}</b> ({zone_desc})</td>
                </tr>
                <tr>
                    <td class="label">Alert Identifier</td>
                    <td class="value"><code>{alert_id}</code></td>
                </tr>
                <tr>
                    <td class="label">Dispatch Time</td>
                    <td class="value">{timestamp}</td>
                </tr>
            </table>
        </div>
        <div class="footer">
            CrowdPatrol Autonomous Surveillance System &bull; Please do not reply directly to this automated email.
        </div>
    </div>
</body>
</html>
"""


def format_alert_email_text(alert: Any) -> str:
    """Generates plain text email body for text-only clients."""
    sev = getattr(alert, "severity", getattr(alert, "risk_level", "HIGH")).upper()
    cat = getattr(alert, "category", "CROWD_RISK")
    cam_id = getattr(alert, "camera_id", "UNKNOWN")
    cam_name = getattr(alert, "camera_name", "Monitored Zone")
    alert_id = getattr(alert, "alert_id", "ALT_UNKNOWN")
    score = float(getattr(alert, "risk_score", 0.0))
    density = int(getattr(alert, "crowd_density", getattr(alert, "primary_zone_density", 0)))
    count = int(getattr(alert, "person_count", 0))
    zone = getattr(alert, "primary_risk_zone", "A1")
    zone_desc = getattr(alert, "zone_description", "Monitored Cell")
    reason = getattr(alert, "reason", "Abnormal crowd activity detected.")
    timestamp = str(getattr(alert, "timestamp", datetime.now().isoformat()))[:19].replace("T", " ")

    return (
        f"=== [CROWDPATROL {sev} ALERT] ===\n\n"
        f"Severity: {sev}\n"
        f"Category: {cat}\n"
        f"Camera: {cam_id} ({cam_name})\n"
        f"Timestamp: {timestamp}\n"
        f"Risk Score: {score:.1f}\n"
        f"Peak Density: {density} persons/cell in Zone {zone} ({zone_desc})\n"
        f"Person/Head Count: {count}\n"
        f"Reason: {reason}\n"
        f"Alert ID: {alert_id}\n\n"
        f"-- CrowdPatrol Autonomous Surveillance System"
    )


def format_alert_sms_text(alert: Any) -> str:
    """Generates concise SMS notification text (<= 160 characters target)."""
    sev = getattr(alert, "severity", getattr(alert, "risk_level", "CRITICAL")).upper()
    cam_id = getattr(alert, "camera_id", "CAM")
    cam_name = getattr(alert, "camera_name", "")
    reason = getattr(alert, "reason", "High crowd risk")
    score = float(getattr(alert, "risk_score", 0.0))
    density = int(getattr(alert, "crowd_density", getattr(alert, "primary_zone_density", 0)))
    zone = getattr(alert, "primary_risk_zone", "A1")
    alert_id = getattr(alert, "alert_id", "")
    timestamp = str(getattr(alert, "timestamp", datetime.now().strftime("%H:%M:%S")))[11:19] if "T" in str(getattr(alert, "timestamp", "")) else str(getattr(alert, "timestamp", ""))[:19]

    # Truncate reason if needed
    if len(reason) > 45:
        reason = reason[:42] + "..."

    cam_str = f"{cam_id}" if not cam_name else f"{cam_id}/{cam_name[:8]}"
    return (
        f"🚨[CrowdPatrol {sev}] {cam_str}: {reason} | "
        f"Score:{score:.1f} Dens:{density}p(Z:{zone}) @{timestamp} ID:{alert_id}"
    )


# ==============================================================================
# Delivery Services
# ==============================================================================

class EmailService:
    """Handles SMTP connection, TLS handshake, authentication, and message dispatch."""

    def __init__(self, config: NotificationConfig):
        self.config = config

    def send_email(
        self,
        subject: str,
        html_body: str,
        text_body: str,
        recipients: Optional[List[str]] = None
    ) -> bool:
        """
        Transmits email to specified recipients using configured SMTP settings.
        Raises specific exceptions on failure so retries and logging can occur.
        """
        targets = recipients or self.config.email_recipients
        if not targets:
            raise ValueError("No email recipients specified")

        if not self.config.smtp_host or not self.config.smtp_port:
            raise ValueError("SMTP host and port must be configured")

        sender = self.config.email_sender or self.config.smtp_username or "alerts@crowdpatrol.local"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(targets)
        msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")

        # Attach text part then HTML part
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        server = None
        try:
            server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=10.0)
            if self.config.smtp_use_tls:
                server.starttls()
            if self.config.smtp_username and self.config.smtp_password:
                server.login(self.config.smtp_username, self.config.smtp_password)
            server.sendmail(sender, targets, msg.as_string())
            return True
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass


class SMSService:
    """Handles Twilio SMS transmission via either official twilio SDK or direct REST API."""

    def __init__(self, config: NotificationConfig):
        self.config = config

    def send_sms(self, message_text: str, recipients: Optional[List[str]] = None) -> bool:
        """
        Transmits SMS message to recipients.
        Uses TwilioRestClient if installed, otherwise falls back to Twilio REST API via requests.
        """
        targets = recipients or self.config.sms_recipients
        if not targets:
            raise ValueError("No SMS recipients specified")

        account_sid = self.config.twilio_account_sid
        auth_token = self.config.twilio_auth_token
        from_num = self.config.twilio_phone_number

        if not account_sid or not auth_token or not from_num:
            raise ValueError("Twilio credentials (Account SID, Auth Token, Sender Number) not fully configured")

        # Method 1: Official twilio SDK if available
        if TWILIO_AVAILABLE and TwilioRestClient is not None:
            client = TwilioRestClient(account_sid, auth_token)
            for recipient in targets:
                client.messages.create(
                    to=recipient,
                    from_=from_num,
                    body=message_text
                )
            return True

        # Method 2: Direct REST API via requests
        if REQUESTS_AVAILABLE:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            for recipient in targets:
                resp = requests.post(
                    url,
                    auth=(account_sid, auth_token),
                    data={"From": from_num, "To": recipient, "Body": message_text},
                    timeout=10.0
                )
                if resp.status_code not in (200, 201):
                    raise RuntimeError(f"Twilio API error HTTP {resp.status_code}: {resp.text}")
            return True

        raise RuntimeError("Neither 'twilio' library nor 'requests' library available for SMS dispatch")


# ==============================================================================
# Asynchronous Notification Dispatcher
# ==============================================================================

class NotificationDispatcher:
    """
    Central Asynchronous Notification Dispatcher.
    
    Guarantees:
    - Never blocks the video inference loop (queue-based background worker).
    - Deduplicates identical alert dispatches using alert_id.
    - Permits immediate dispatch for escalated severity.
    - Routes by severity (e.g. HIGH -> email, CRITICAL -> email + SMS).
    - Retries transient errors with bounded backoff.
    - Maintains delivery log and diagnostic status metrics.
    """

    def __init__(
        self,
        config: Optional[NotificationConfig] = None,
        email_service: Optional[EmailService] = None,
        sms_service: Optional[SMSService] = None,
        autostart_worker: bool = True
    ):
        self.config = config or NotificationConfig.from_env()
        self.email_service = email_service or EmailService(self.config)
        self.sms_service = sms_service or SMSService(self.config)

        # Work queue: tuples of (alert_event, channel, attempt_count)
        self._queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Deduplication tracking: set of f"{alert_id}:{channel}"
        self._dispatched_alert_keys: Set[str] = set()
        # Track highest severity dispatched per camera: {cam_id: rank}
        self._camera_highest_severity: Dict[str, str] = {}

        # History log: last 200 delivery attempts
        self.history: deque = deque(maxlen=200)

        # Performance / status counters
        self.total_sent: int = 0
        self.total_failed: int = 0
        self.last_attempt_time: Optional[str] = None
        self.last_attempt_status: Optional[str] = None
        self.last_attempt_channel: Optional[str] = None

        self._worker_thread: Optional[threading.Thread] = None
        if autostart_worker:
            self.start()

    def start(self):
        """Starts background worker thread if not already running."""
        with self._lock:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._stop_event.clear()
                self._worker_thread = threading.Thread(
                    target=self._worker_loop,
                    name="CrowdPatrol-NotificationWorker",
                    daemon=True
                )
                self._worker_thread.start()

    def stop(self, timeout: float = 2.0):
        """Gracefully halts background worker thread after allowing queue to drain."""
        t0 = time.time()
        while not self._queue.empty() and (time.time() - t0 < timeout):
            time.sleep(0.02)
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            remain = max(0.2, timeout - (time.time() - t0))
            self._worker_thread.join(timeout=remain)
            self._worker_thread = None

    def dispatch_alert(self, alert: Any) -> Dict[str, str]:
        """
        Main non-blocking entry point: evaluates alert severity and routes
        to email and/or SMS background queue.
        
        Returns immediate route decision dict, e.g.:
        {"email": "QUEUED", "sms": "SKIPPED"}
        """
        if not self.config.enabled:
            return {"email": "DISABLED", "sms": "DISABLED"}

        sev = getattr(alert, "severity", getattr(alert, "risk_level", "LOW")).upper()
        alert_id = getattr(alert, "alert_id", "")
        cam_id = getattr(alert, "camera_id", "CAM")

        results = {}

        # 1. Email Evaluation
        if sev in self.config.email_severities:
            email_key = f"{alert_id}:EMAIL"
            with self._lock:
                already_sent = email_key in self._dispatched_alert_keys

            if already_sent:
                results["email"] = "SUPPRESSED_DUPLICATE"
            else:
                if not self.config.is_email_configured:
                    results["email"] = "SKIPPED_NOT_CONFIGURED"
                    self._record_outcome(
                        alert_id=alert_id,
                        camera_id=cam_id,
                        channel="EMAIL",
                        recipient=", ".join(self.config.email_recipients) or "(none)",
                        severity=sev,
                        status="SKIPPED",
                        error_message="SMTP credentials not configured"
                    )
                else:
                    with self._lock:
                        self._dispatched_alert_keys.add(email_key)
                    self._queue.put((alert, "EMAIL", 1))
                    results["email"] = "QUEUED"
        else:
            results["email"] = "FILTERED_SEVERITY"

        # 2. SMS Evaluation
        if sev in self.config.sms_severities:
            sms_key = f"{alert_id}:SMS"
            with self._lock:
                already_sent = sms_key in self._dispatched_alert_keys

            if already_sent:
                results["sms"] = "SUPPRESSED_DUPLICATE"
            else:
                if not self.config.is_sms_configured:
                    results["sms"] = "SKIPPED_NOT_CONFIGURED"
                    self._record_outcome(
                        alert_id=alert_id,
                        camera_id=cam_id,
                        channel="SMS",
                        recipient=", ".join(self.config.sms_recipients) or "(none)",
                        severity=sev,
                        status="SKIPPED",
                        error_message="Twilio credentials not configured"
                    )
                else:
                    with self._lock:
                        self._dispatched_alert_keys.add(sms_key)
                    self._queue.put((alert, "SMS", 1))
                    results["sms"] = "QUEUED"
        else:
            results["sms"] = "FILTERED_SEVERITY"

        return results

    def as_alert_listener(self) -> Callable[[Any], None]:
        """
        Returns a listener callback compatible with AlertManager.register_listener.
        Only dispatches on ACTIVE or ESCALATED alerts, ignoring resolved or ack transitions.
        """
        def _listener(alert: Any):
            status = getattr(alert, "status", "ACTIVE")
            if status in ("ACTIVE", "ESCALATED"):
                self.dispatch_alert(alert)
        return _listener

    def _worker_loop(self):
        """Continuous background worker loop processing notification tasks."""
        while not self._stop_event.is_set():
            try:
                task = self._queue.get(timeout=self.config.queue_timeout)
            except queue.Empty:
                continue

            alert, channel, attempt = task
            sev = getattr(alert, "severity", getattr(alert, "risk_level", "HIGH")).upper()
            alert_id = getattr(alert, "alert_id", "ALT")
            cam_id = getattr(alert, "camera_id", "CAM")

            target_repr = ", ".join(self.config.email_recipients) if channel == "EMAIL" else ", ".join(self.config.sms_recipients)
            success = False
            err_msg = None

            try:
                if channel == "EMAIL":
                    subject = f"🚨 [CrowdPatrol {sev}] Alert on Camera {cam_id} - Score: {getattr(alert, 'risk_score', 0.0):.1f}"
                    html_body = format_alert_email_html(alert)
                    text_body = format_alert_email_text(alert)
                    success = self.email_service.send_email(subject, html_body, text_body)
                elif channel == "SMS":
                    sms_text = format_alert_sms_text(alert)
                    success = self.sms_service.send_sms(sms_text)
                else:
                    raise ValueError(f"Unknown channel: {channel}")
            except Exception as e:
                success = False
                err_msg = str(e)

            if success:
                self._record_outcome(
                    alert_id=alert_id,
                    camera_id=cam_id,
                    channel=channel,
                    recipient=target_repr,
                    severity=sev,
                    status="SENT",
                    attempts=attempt
                )
                self._queue.task_done()
            else:
                # Handle retries
                if attempt < self.config.max_retries and not self._stop_event.is_set():
                    backoff = self.config.retry_backoff * (2 ** (attempt - 1))
                    # Non-blocking re-enqueue with delay simulation
                    time.sleep(min(backoff, 2.0))
                    self._queue.put((alert, channel, attempt + 1))
                    self._record_outcome(
                        alert_id=alert_id,
                        camera_id=cam_id,
                        channel=channel,
                        recipient=target_repr,
                        severity=sev,
                        status="RETRYING",
                        attempts=attempt,
                        error_message=f"{err_msg} (will retry attempt {attempt + 1})"
                    )
                    self._queue.task_done()
                else:
                    self._record_outcome(
                        alert_id=alert_id,
                        camera_id=cam_id,
                        channel=channel,
                        recipient=target_repr,
                        severity=sev,
                        status="FAILED",
                        attempts=attempt,
                        error_message=err_msg
                    )
                    self._queue.task_done()

    def _record_outcome(
        self,
        alert_id: str,
        camera_id: str,
        channel: str,
        recipient: str,
        severity: str,
        status: str,
        attempts: int = 1,
        error_message: Optional[str] = None
    ):
        """Internal helper to record delivery history and update KPI counters."""
        now_iso = datetime.now().isoformat()
        record = NotificationRecord(
            record_id=f"NOTIF_{int(time.time()*1000)}_{channel[:3]}",
            alert_id=alert_id,
            camera_id=camera_id,
            channel=channel,
            recipient=recipient,
            severity=severity,
            timestamp=now_iso,
            status=status,
            attempts=attempts,
            error_message=error_message
        )
        with self._lock:
            self.history.append(record)
            self.last_attempt_time = now_iso
            self.last_attempt_status = status
            self.last_attempt_channel = channel

            if status == "SENT":
                self.total_sent += 1
            elif status == "FAILED":
                self.total_failed += 1

    def get_history(
        self,
        limit: int = 50,
        channel: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[NotificationRecord]:
        """Returns filtered slice of delivery records in reverse chronological order."""
        with self._lock:
            records = list(self.history)

        filtered = []
        for r in reversed(records):
            if channel and r.channel.upper() != channel.upper():
                continue
            if status and r.status.upper() != status.upper():
                continue
            filtered.append(r)
            if len(filtered) >= limit:
                break
        return filtered

    def get_status_summary(self) -> Dict[str, Any]:
        """Provides status summary for dashboard telemetry display."""
        with self._lock:
            q_size = self._queue.qsize()
            return {
                "enabled": self.config.enabled,
                "is_email_configured": self.config.is_email_configured,
                "is_sms_configured": self.config.is_sms_configured,
                "total_sent": self.total_sent,
                "total_failed": self.total_failed,
                "pending_queue_size": q_size,
                "last_attempt_time": self.last_attempt_time,
                "last_attempt_status": self.last_attempt_status,
                "last_attempt_channel": self.last_attempt_channel,
                "config_safe": self.config.to_safe_dict()
            }

    # ==========================================================================
    # Explicit Test Actions
    # ==========================================================================

    def send_test_email(self, to_email: Optional[str] = None) -> Tuple[bool, str]:
        """Sends an immediate test email verification message."""
        if not self.config.is_email_configured and not to_email:
            return False, "SMTP is not fully configured in environment or .env"

        recipients = [to_email.strip()] if to_email else self.config.email_recipients
        subject = "🧪 [CrowdPatrol Test] Email Integration Verification"
        text_body = (
            "=== CrowdPatrol Test Notification ===\n\n"
            "This is a verification test message confirming SMTP email notification delivery.\n"
            f"Timestamp: {datetime.now().isoformat()}\n"
            "If you received this message, your email dispatch system is operational."
        )
        html_body = f"""
        <div style="font-family:sans-serif; max-width:500px; margin:auto; padding:20px; border:1px solid #ddd; border-radius:8px;">
            <h2 style="color:#0066cc; margin-top:0;">🧪 CrowdPatrol Test Email</h2>
            <p>This test verification confirms that your <b>SMTP Email Notification System</b> is correctly configured and operational.</p>
            <table style="width:100%; border-collapse:collapse; margin-top:15px;">
                <tr><td style="padding:6px; color:#666;">SMTP Host:</td><td><b>{self.config.smtp_host}</b></td></tr>
                <tr><td style="padding:6px; color:#666;">Sender:</td><td><b>{self.config.email_sender}</b></td></tr>
                <tr><td style="padding:6px; color:#666;">Timestamp:</td><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
            </table>
            <p style="margin-top:20px; font-size:12px; color:#888;">CrowdPatrol Automated Surveillance Engine</p>
        </div>
        """
        try:
            ok = self.email_service.send_email(subject, html_body, text_body, recipients=recipients)
            self._record_outcome(
                alert_id="TEST_EMAIL",
                camera_id="SYSTEM",
                channel="EMAIL",
                recipient=", ".join(recipients),
                severity="TEST",
                status="SENT"
            )
            return True, f"Test email successfully sent to {', '.join(recipients)}"
        except Exception as e:
            self._record_outcome(
                alert_id="TEST_EMAIL",
                camera_id="SYSTEM",
                channel="EMAIL",
                recipient=", ".join(recipients),
                severity="TEST",
                status="FAILED",
                error_message=str(e)
            )
            return False, f"Failed to send test email: {e}"

    def send_test_sms(self, to_phone: Optional[str] = None) -> Tuple[bool, str]:
        """Sends an immediate test SMS verification message."""
        if not self.config.is_sms_configured and not to_phone:
            return False, "Twilio SMS is not fully configured in environment or .env"

        recipients = [to_phone.strip()] if to_phone else self.config.sms_recipients
        msg_text = f"🧪[CrowdPatrol Test] SMS delivery test verified at {datetime.now().strftime('%H:%M:%S')}."
        try:
            ok = self.sms_service.send_sms(msg_text, recipients=recipients)
            self._record_outcome(
                alert_id="TEST_SMS",
                camera_id="SYSTEM",
                channel="SMS",
                recipient=", ".join(recipients),
                severity="TEST",
                status="SENT"
            )
            return True, f"Test SMS successfully sent to {', '.join(recipients)}"
        except Exception as e:
            self._record_outcome(
                alert_id="TEST_SMS",
                camera_id="SYSTEM",
                channel="SMS",
                recipient=", ".join(recipients),
                severity="TEST",
                status="FAILED",
                error_message=str(e)
            )
            return False, f"Failed to send test SMS: {e}"


# Singleton instance accessor for application-wide sharing
_GLOBAL_DISPATCHER: Optional[NotificationDispatcher] = None

def get_notification_dispatcher() -> NotificationDispatcher:
    """Returns application singleton NotificationDispatcher instance."""
    global _GLOBAL_DISPATCHER
    if _GLOBAL_DISPATCHER is None:
        _GLOBAL_DISPATCHER = NotificationDispatcher()
    return _GLOBAL_DISPATCHER

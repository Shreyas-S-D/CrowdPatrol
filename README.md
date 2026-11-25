# CROWDPatrol — AI-Powered Crowd Safety & Surveillance

**Intelligent crowd monitoring, anomaly detection, and real-time security alerts.**

CROWDPatrol is an AI-powered crowd surveillance and safety monitoring system designed to help identify potentially dangerous situations in crowded environments. It combines computer vision, object detection, motion analysis, and alert management to support proactive security monitoring.

The goal is to move beyond traditional passive CCTV monitoring by using AI to assist operators in identifying unusual crowd activity and responding to potential incidents.

---

## Key Features

- **AI-Based Crowd Detection:** Uses YOLO-based object detection to identify and monitor people in video feeds.
- **Anomaly Detection:** Analyzes movement patterns and detection-related signals to identify potentially abnormal activity.
- **Real-Time Monitoring:** Provides a live surveillance dashboard for monitoring camera feeds.
- **Dynamic Risk Assessment:** Combines tracking and motion-related anomaly signals to calculate risk scores.
- **Alert Management:** Supports alert acknowledgement and resolution for high- and critical-priority incidents.
- **Audio Notifications:** Browser-based sound alerts for high- and critical-severity events.
- **Multi-Camera Support:** Designed to support monitoring across multiple camera feeds.
- **User Authentication:** Includes account registration and email OTP verification.
- **Multi-Tenant Architecture:** Supports isolated camera configurations, alert records, and notification routing for different users or organizations.
- **Performance Evaluation:** Includes benchmarking, detection evaluation, and validation scripts.

## Technology Stack

| Component | Technologies |
|---|---|
| Programming Language | Python, JavaScript |
| AI & Computer Vision | YOLOv8, OpenCV |
| Dashboard | Streamlit |
| Frontend | React, Vite |
| Backend | Python-based API services |
| Authentication | Email OTP verification |
| Database / Storage | Project-configured database and Firebase integration |
| Version Control | Git, GitHub |

## Project Structure

```text
CROWDPatrol/
│
├── .agents/
│   └── skills/
│
├── backend/
│   ├── routers/
│   └── services/
│
├── frontend/
│   ├── public/
│   └── src/
│       ├── components/
│       ├── services/
│       └── assets/
│
├── scripts/
│   ├── benchmarking/
│   ├── evaluation/
│   └── validation/
│
├── tools/
│
├── dashboard/
│
├── reports/
│
├── .gitignore
└── README.md
```

*The structure above highlights the major project components; individual files and supporting directories may vary.*

## Getting Started

### Prerequisites

- Python 3.10 or later
- Node.js and npm
- Git
- Webcam or compatible video source for live monitoring

### Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd CrowdPatrol
```

### Python Environment

```bash
python -m venv venv
```

Activate the environment:

**Windows:**
```bash
venv\Scripts\activate
```

**Linux / macOS:**
```bash
source venv/bin/activate
```

Install the project's Python dependencies using its requirements file, if provided:

```bash
pip install -r requirements.txt
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Run the Dashboard

Launch the Streamlit dashboard using the entry-point script configured for your project:

```bash
streamlit run dashboard/simple_dashboard.py
```

> Configure the required environment variables, database connections, model weights, and Firebase credentials before running the application. Never commit credentials or secret configuration files to GitHub.

## Research & Evaluation

CROWDPatrol includes dedicated scripts and reports for evaluating detection accuracy, inference performance, system behavior, and security.

Evaluation areas include:

- Object detection performance
- Crowd detection accuracy
- Inference speed and frame processing
- CPU and threading behavior
- Alert lifecycle validation
- Authentication and tenant-isolation security

## Security

Security is an important part of the project.

- Email-based OTP verification
- User-specific monitoring configurations
- Isolated alert management
- Credential and secret protection
- Authentication and authorization validation
- Security testing and audit documentation

## Project Documentation

The repository includes technical documentation covering:

- System architecture
- Authentication design
- Multi-tenancy design
- Implementation planning
- Security audits and corrections
- Performance validation
- Phase-wise development reports

## Project Status

**Active Development — CrowdPatrol 2.0**

The project is being developed incrementally, with ongoing improvements to detection performance, monitoring capabilities, security, and system architecture.

## Contributors

Developed as an undergraduate Computer Science and Engineering major project specializing in Artificial Intelligence and Machine Learning.

---

**CROWDPatrol — Smarter Surveillance. Safer Crowds.**

# CrowdPatrol --- Project Context

## 1. Project Identity

**Project Title:** CrowdPatrol: Autonomous Public Safety & Monitoring
Core\
**Project Type:** B.E. Major Project --- Phase 1\
**Department:** Computer Science and Engineering (AI & ML)\
**Institution:** AMC Engineering College\
**Team:** Team 21

## 2. Project Overview

CrowdPatrol is an AI-driven crowd monitoring and public safety system
intended to analyze live camera feeds and recorded videos. The system
detects and tracks people, estimates crowd density, calculates a risk
score, and presents monitoring information through a dashboard.

The long-term goal is to support proactive crowd management by
identifying potentially dangerous crowd conditions earlier than manual
surveillance alone.

## 3. Problem Being Addressed

Traditional crowd surveillance depends heavily on security personnel and
basic CCTV recording. These approaches can be:

-   Limited in coverage.
-   Reactive rather than preventive.
-   Affected by human fatigue and cognitive overload.
-   Unable to automatically analyze crowd movement and density.
-   Expensive or inaccessible when using proprietary commercial
    analytics systems.

CrowdPatrol aims to provide an accessible, AI-based monitoring and
risk-assessment platform.

## 4. Main Objectives

1.  Detect people in real time using YOLOv8.
2.  Track detected people across video frames using DeepSORT.
3.  Estimate crowd density using a grid-based approach.
4.  Analyze crowd conditions and calculate a risk score.
5.  Classify risk into Low, Medium, or High.
6.  Synchronize monitoring data using Firebase Realtime Database.
7.  Display live analytics through a Streamlit dashboard.
8.  Add movement analysis, automated alerts, and stronger evaluation in
    later stages.

## 5. Proposed System Workflow

1.  Receive input from a live camera, CCTV/IP camera, or recorded video.
2.  Extract and process video frames using OpenCV.
3.  Detect people using YOLOv8.
4.  Track people using DeepSORT and assign tracking IDs.
5.  Count people and estimate density across grid regions.
6.  Calculate anomaly/risk-related values.
7.  Classify the current risk level.
8.  Send relevant metrics to Firebase Realtime Database.
9.  Display results through the Streamlit dashboard.
10. Trigger alerts when properly defined thresholds are crossed.

## 6. Technology Stack

-   **Programming language:** Python
-   **Computer vision:** OpenCV
-   **Object detection:** Ultralytics YOLOv8
-   **Multi-object tracking:** DeepSORT
-   **Numerical processing:** NumPy
-   **Deep learning ecosystem:** PyTorch and/or related libraries used
    by the implementation
-   **Backend/data synchronization:** Firebase Realtime Database
-   **Dashboard:** Streamlit
-   **Development tools:** VS Code and related Python tooling

## 7. Important Design Concepts

### Person Detection

YOLOv8 is used to identify people in each processed frame.

### Multi-Object Tracking

DeepSORT associates detections across frames and assigns unique IDs to
tracked people.

### Grid-Based Density Estimation

The frame is divided into regions. The number of detected people in each
region is used to estimate local crowd density.

### Risk Assessment

The current implementation uses density and anomaly-related values to
calculate a risk score and classify the scene as Low, Medium, or High
risk.

### Movement Analysis --- Planned Enhancement

Optical flow is intended to estimate crowd movement direction and speed
and to identify sudden or abnormal movement patterns.

## 8. Important Development Rule

This is an existing project. Do not rebuild the project from scratch.

Before making changes:

-   Inspect the existing repository.
-   Identify the actual entry points.
-   Run the current implementation.
-   Verify which modules work.
-   Preserve working code.
-   Make small, testable changes.
-   Document all modifications.

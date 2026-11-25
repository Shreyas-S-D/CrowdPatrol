# Instructions for Antigravity --- CrowdPatrol

You are assisting with an existing B.E. major project named
**CrowdPatrol: Autonomous Public Safety & Monitoring Core**.

## Read These Files First

Read the following files before inspecting or changing code:

1.  `PROJECT_CONTEXT.md`
2.  `IMPLEMENTATION_STATUS.md`
3.  `DEVELOPMENT_ROADMAP.md`

## Your Working Principles

-   Treat the repository as an existing working prototype.
-   Do not rebuild the project from scratch.
-   Do not assume that a feature is missing merely because it is listed
    as pending.
-   Verify the actual code and run the application before making
    changes.
-   Preserve working functionality.
-   Make one small, testable change at a time.
-   Explain which files will be changed and why.
-   Avoid unnecessary dependency changes.
-   Do not fabricate results, metrics, screenshots, or successful tests.
-   If a feature cannot be tested, clearly state that.
-   Keep configuration values explicit and easy to modify.
-   Add useful comments, but do not over-comment obvious code.
-   Handle errors gracefully.
-   Do not expose secrets, API keys, Firebase credentials, or private
    configuration values.

## First Task: Audit the Repository

Before editing code, produce a concise report containing:

### A. Project Structure

List the important folders and files.

### B. Execution

Identify:

-   Main entry point.
-   Commands needed to run the detector.
-   Commands needed to run the dashboard.
-   Required environment variables or configuration.
-   Dependency installation steps.

### C. Feature Verification

For each feature below, mark it as:

-   Working
-   Partially working
-   Broken
-   Not found
-   Not tested

Features:

-   YOLOv8 detection.
-   DeepSORT tracking.
-   Person counting.
-   Grid-based density estimation.
-   Heatmap visualization.
-   Risk-score calculation.
-   Low/Medium/High risk classification.
-   Firebase integration.
-   Streamlit dashboard.
-   Live camera input.
-   Recorded-video input.
-   Video output saving.
-   External camera support.
-   Automated alerts.
-   Optical flow.

### D. Performance Baseline

Measure or report:

-   Current FPS.
-   Input resolution.
-   Model used.
-   CPU/GPU status.
-   Approximate processing latency.
-   Any obvious bottleneck.

### E. Recommended Next Change

Recommend the smallest safe change based on the audit.

## Required Approval Point

After completing the audit, stop and present:

1.  What you found.
2.  What is already working.
3.  What is incomplete.
4.  Which files should be modified.
5.  What the first change will do.
6.  How it will be tested.

Do not begin major implementation until the plan is reviewed.

## Development Sequence

Unless the repository audit reveals a more urgent blocker, follow this
sequence:

1.  Performance profiling and FPS optimization.
2.  Optical flow implementation.
3.  Risk engine improvement.
4.  Automated alerts.
5.  Dashboard refinement.
6.  Systematic testing and evaluation.
7.  Final documentation.

## Definition of Done for Each Change

A change is complete only when:

-   The code runs without new errors.
-   Existing functionality still works.
-   The change has been tested with at least one relevant input.
-   The result is documented.
-   Any limitations are clearly stated.

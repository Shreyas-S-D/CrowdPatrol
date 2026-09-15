# CrowdPatrol --- Development Roadmap

## Overall Strategy

Continue from the existing implementation. Work incrementally, test
every change, and avoid rewriting working modules.

## Phase 0 --- Repository Inspection

Before coding:

1.  Inspect the complete project tree.
2.  Identify the main execution file or command.
3.  Identify detection, tracking, density, risk, Firebase, dashboard,
    and alert modules.
4.  Read the README and configuration files.
5.  Install or verify dependencies.
6.  Run the existing system.
7.  Record errors and current FPS.
8.  Create a short technical assessment before making modifications.

**Deliverable:** A repository audit containing file paths, current
behavior, problems, and a safe implementation plan.

## Phase 1 --- Performance Optimization

### Goals

-   Improve FPS.
-   Reduce unnecessary computation.
-   Preserve detection and tracking quality.
-   Avoid excessive database and dashboard updates.

### Investigation Areas

-   Model size and inference settings.
-   Input resolution.
-   Frame skipping or controlled processing rate.
-   CPU versus GPU execution.
-   Detection confidence and IoU thresholds.
-   DeepSORT configuration.
-   Drawing and logging overhead.
-   Firebase write frequency.
-   Dashboard refresh frequency.

### Deliverables

-   Before-and-after FPS measurements.
-   CPU/GPU usage observations where possible.
-   Updated code with comments.
-   No regression in existing functionality.

## Phase 2 --- Optical Flow Analysis

### Goals

Implement movement analysis using optical flow.

### Features

-   Estimate motion vectors between frames.
-   Calculate approximate movement direction.
-   Estimate movement magnitude or speed.
-   Aggregate motion across grid regions.
-   Identify sudden changes in movement.
-   Handle invalid frames and noisy motion.

### Important Considerations

-   Test more than one optical-flow method if useful.
-   Avoid treating every large movement as dangerous.
-   Account for camera motion where possible.
-   Clearly distinguish movement indication from confirmed panic or
    stampede detection.

### Deliverables

-   Optical-flow module.
-   Visual overlay showing motion direction or magnitude.
-   Sample outputs.
-   Basic tests.
-   Explanation of assumptions and limitations.

## Phase 3 --- Risk Assessment Upgrade

### Goals

Combine multiple signals into a transparent and configurable risk
engine.

Possible inputs:

-   Total person count.
-   Local grid density.
-   Maximum regional density.
-   Movement magnitude.
-   Sudden movement changes.
-   Anomaly-related score.
-   Optional persistence over multiple frames.

### Requirements

-   Keep the scoring formula understandable.
-   Store thresholds in configuration where practical.
-   Avoid abrupt risk changes caused by one noisy frame.
-   Consider temporal smoothing.
-   Log the individual factors contributing to the final risk score.

### Deliverables

-   Updated risk engine.
-   Documented formula.
-   Configurable thresholds.
-   Example Low, Medium, and High risk scenarios.
-   Tests for boundary values.

## Phase 4 --- Automated Alerts

### Goals

Trigger alerts only when risk conditions are satisfied.

### Requirements

-   Define alert thresholds.
-   Require a condition to persist for a configurable duration or number
    of frames.
-   Avoid sending duplicate alerts continuously.
-   Record alert time, risk level, score, and reason.
-   Handle Firebase/network failures gracefully.
-   Provide a cooldown period.
-   Keep alert functionality disabled by default until tested.

### Possible Channels

-   Firebase-based notification workflow.
-   Email.
-   SMS.
-   Push notifications.

Use only the channels that are actually configured and tested in the
repository.

## Phase 5 --- Dashboard Improvements

### Goals

Present the system state clearly to an operator.

Potential additions:

-   Live risk level and score.
-   Person count.
-   Maximum regional density.
-   FPS and processing latency.
-   Heatmap.
-   Movement visualization.
-   Risk trend chart.
-   Alert history.
-   System connection status.
-   Camera/video source information.

The dashboard must not display fabricated or stale values without
indicating their status.

## Phase 6 --- Testing and Evaluation

### Test Categories

1.  Empty or low-density scenes.
2.  Moderate-density scenes.
3.  High-density scenes.
4.  Indoor scenes.
5.  Outdoor scenes.
6.  Different lighting conditions.
7.  Occlusion-heavy scenes.
8.  Camera movement.
9.  Sudden crowd movement.
10. Network/database interruption.

### Metrics

-   FPS.
-   End-to-end latency.
-   Detection precision and recall, when labels are available.
-   Tracking stability.
-   Person-count error.
-   Density-estimation consistency.
-   Risk-classification results.
-   False-positive and false-negative alert counts.

### Deliverables

-   Test dataset/video list.
-   Test procedure.
-   Results table.
-   Graphs where appropriate.
-   Limitations and failure cases.

## Phase 7 --- Final Documentation

Prepare:

-   Detailed implementation chapter.
-   System architecture.
-   Module descriptions.
-   Dataset and testing details.
-   Screenshots and output examples.
-   Performance tables.
-   Limitations.
-   Future scope.
-   Conclusion.
-   Proper references.

## Immediate Next Task

The first actual coding task is **not** optical flow or a rewrite.

The immediate task is:

> Inspect and run the existing repository, verify the implementation
> status, measure current FPS, identify the bottleneck, and propose the
> smallest safe performance-improvement change.

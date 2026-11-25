"""
tests/test_production_network_probe_safety.py
---------------------------------------------
Comprehensive automated validation of production network camera probe safety:
1. Valid local video verification.
2. Unreachable IP camera handling with bounded timeout.
3. Invalid RTSP endpoint handling (closed port / invalid stream).
4. Repeated failed connection attempts without thread accumulation.
5. Successful connection after a failed attempt.
6. Resource cleanup and thread lifecycle verification.
7. Verification that TCP reachability alone does not mark an invalid RTSP stream as valid.
"""

import time
import socket
import threading
from pathlib import Path
import cv2
import numpy as np
import pytest

from src.camera_devices import verify_stream_source, _active_network_probes, _active_network_probes_lock


def test_probe_valid_local_video():
    """Verify that a valid local video file is opened, verified, and its handle released."""
    sample_video = "data/videos/crowd_sample.mp4"
    assert Path(sample_video).exists(), f"Sample video {sample_video} not found"
    
    ok, msg, res, status = verify_stream_source(sample_video, timeout_sec=2.0, source_type="preset_video")
    assert ok is True
    assert status == "CONNECTED"
    assert res != "0x0"
    assert "verified" in msg.lower() or "connected" in msg.lower()


def test_probe_unreachable_ip_camera_bounded_timeout():
    """Verify that an unreachable IP camera returns within configured timeout bounds and never hangs."""
    t0 = time.time()
    ok, msg, res, status = verify_stream_source(
        "rtsp://198.51.100.1:554/live",
        timeout_sec=1.0,
        source_type="ip_camera"
    )
    elapsed = time.time() - t0
    assert ok is False
    assert status in ("CONNECTION_TIMEOUT", "DISCONNECTED")
    assert elapsed < 2.5, f"Probe took too long: {elapsed:.2f}s (must be < 2.5s)"


def test_probe_invalid_rtsp_closed_port():
    """Verify that connecting to an endpoint with a closed port fails promptly with DISCONNECTED or TIMEOUT."""
    # Find an unused local port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    closed_port = sock.getsockname()[1]
    sock.close()

    t0 = time.time()
    ok, msg, res, status = verify_stream_source(
        f"rtsp://127.0.0.1:{closed_port}/live",
        timeout_sec=1.0,
        source_type="ip_camera"
    )
    elapsed = time.time() - t0
    assert ok is False
    assert status in ("DISCONNECTED", "CONNECTION_TIMEOUT")
    assert elapsed < 2.5, f"Closed port probe took too long: {elapsed:.2f}s"


def test_probe_tcp_connectivity_does_not_falsely_validate_invalid_rtsp():
    """
    Verify that an open TCP port that is NOT a valid RTSP stream is NOT marked valid.
    Requirement: do not treat successful TCP connectivity as proof that an RTSP stream is valid.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]
    server.listen(1)

    stop_server = threading.Event()

    def dummy_server():
        try:
            server.settimeout(2.0)
            while not stop_server.is_set():
                try:
                    conn, _ = server.accept()
                    # Keep connection open briefly then close
                    time.sleep(0.3)
                    conn.close()
                except socket.timeout:
                    break
        except Exception:
            pass
        finally:
            server.close()

    srv_thread = threading.Thread(target=dummy_server, daemon=True)
    srv_thread.start()

    try:
        t0 = time.time()
        ok, msg, res, status = verify_stream_source(
            f"rtsp://127.0.0.1:{port}/live",
            timeout_sec=1.5,
            source_type="ip_camera"
        )
        elapsed = time.time() - t0
        # TCP connection was established, but stream is NOT a valid RTSP stream!
        # Must return ok=False and status != CONNECTED
        assert ok is False
        assert status in ("DISCONNECTED", "CONNECTION_TIMEOUT", "FAILED")
        assert elapsed < 3.0
    finally:
        stop_server.set()
        srv_thread.join(timeout=1.0)


def test_probe_repeated_failed_connection_attempts():
    """Verify that repeated failed connection attempts do not stack threads or leak resources."""
    initial_threads = threading.active_count()

    for i in range(3):
        t0 = time.time()
        ok, msg, res, status = verify_stream_source(
            "rtsp://198.51.100.1:554/live",
            timeout_sec=1.0,
            source_type="ip_camera"
        )
        elapsed = time.time() - t0
        assert ok is False
        assert status in ("CONNECTION_TIMEOUT", "DISCONNECTED")
        assert elapsed < 2.5

    # Small pause for daemon thread cleanup
    time.sleep(0.3)
    final_threads = threading.active_count()
    # Active thread count must not increase unboundedly with repeated attempts
    assert final_threads <= initial_threads + 1, f"Thread accumulation detected: was {initial_threads}, now {final_threads}"


def test_probe_successful_connection_after_failed_attempt():
    """Verify that a successful connection succeeds cleanly immediately after a failed connection attempt."""
    # 1. Failed attempt
    ok1, _, _, st1 = verify_stream_source("rtsp://198.51.100.1:554/live", timeout_sec=1.0, source_type="ip_camera")
    assert ok1 is False
    assert st1 in ("CONNECTION_TIMEOUT", "DISCONNECTED")

    # 2. Immediate successful attempt on valid local video
    sample_video = "data/videos/crowd_sample.mp4"
    ok2, msg2, res2, st2 = verify_stream_source(sample_video, timeout_sec=2.0, source_type="preset_video")
    assert ok2 is True
    assert st2 == "CONNECTED"
    assert res2 != "0x0"


def test_probe_thread_lifecycle_and_active_probe_table():
    """Verify that in-flight probe table is cleaned up when probes terminate."""
    test_url = "rtsp://198.51.100.1:554/live"
    verify_stream_source(test_url, timeout_sec=1.0, source_type="ip_camera")
    
    # Give thread termination a moment
    time.sleep(0.5)
    with _active_network_probes_lock:
        active_thread = _active_network_probes.get(test_url)
        assert active_thread is None or not active_thread.is_alive()

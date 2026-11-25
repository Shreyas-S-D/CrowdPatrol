import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.dashboard_utils import (
    load_offline_csv_fallback,
    normalize_telemetry_payload,
    evaluate_telemetry_staleness,
    clean_native_value
)

def test_dashboard_components():
    print("==================================================")
    print("   TESTING DASHBOARD HELPER COMPONENTS")
    print("==================================================")
    
    # 1. Test offline CSV fallback loading
    data, log_source = load_offline_csv_fallback(log_dir="logs")
    assert data is not None, "Failed to load telemetry from CSV fallback!"
    print(f"[OK] CSV Fallback Loaded successfully from: {log_source}")
    print(f"    - Payload Keys ({len(data)} keys): {list(data.keys())}")
    
    # 2. Test telemetry payload normalization
    normalized = normalize_telemetry_payload(data)
    assert len(normalized) == 19, f"Expected 19 keys, got {len(normalized)}"
    print(f"[OK] Telemetry Payload Normalization Verified (19 keys):")
    print(f"    - Person Count:         {normalized['person_count']}")
    print(f"    - Max Density:          {normalized['max_density']}")
    print(f"    - Risk Level:           {normalized['risk_level']}")
    print(f"    - Smoothed Risk Score:  {normalized['smoothed_score']}")
    print(f"    - Data Quality Score:   {normalized['data_quality_score']}")
    print(f"    - Growth Rate:          {normalized['growth_rate']}")
    print(f"    - Avg Speed:            {normalized['avg_speed']}")
    print(f"    - Camera Motion:        {normalized['camera_motion_detected']}")
    
    # 3. Test staleness evaluation
    is_stale, age_sec = evaluate_telemetry_staleness(normalized['last_frame_time'])
    print(f"[OK] Staleness Evaluation: Is Stale={is_stale}, Age={age_sec:.2f}s")
    
    print("==================================================")
    print("   [OK] ALL DASHBOARD COMPONENT TESTS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    test_dashboard_components()

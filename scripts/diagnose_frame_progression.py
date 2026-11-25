import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.auth.database import AuthDatabase
from src.multi_camera_manager import MultiCameraManager

def main():
    db = AuthDatabase()
    orgs = db.list_all_organizations()
    if not orgs:
        print("No orgs found")
        return
    org = orgs[0]
    configs = db.get_camera_configs(org.id)
    print(f"Testing with org: {org.id} ({org.name})")
    for c in configs:
        print(f"Slot: {c.slot_id}, type: {c.source_type}, src: {c.source}, enabled: {c.enabled}")

    mc = MultiCameraManager(
        camera_configs=configs,
        detection_mode="PERSON",
        device="cpu",
        detect_interval=3,
        organization_id=org.id,
        session_id="test_diag_sess"
    )

    print("\n--- Starting all cameras ---")
    started = mc.start_all_cameras()
    print(f"Started count: {started}")
    for cid, cam in mc.cameras.items():
        print(f"Cam {cid}: status={cam.status}, cap={type(cam.cap)}, err={cam.error_message}")

    print("\n--- Stepping 10 times ---")
    for step_i in range(1, 11):
        t0 = time.time()
        res = mc.step_all()
        dur = time.time() - t0
        print(f"\nStep {step_i} (took {dur:.3f}s): processed {list(res.keys())}")
        for cid, cam in mc.cameras.items():
            cap_idx = getattr(cam.cap, "current_frame_idx", None) if cam.cap else None
            print(f"  {cid}: status={cam.status}, frame_count={cam.frame_count}, cap_idx={cap_idx}, err={cam.error_message}")

if __name__ == "__main__":
    main()

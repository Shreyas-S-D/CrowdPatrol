import cv2
import numpy as np
import os

def create_rich_crowd_video(output_path="data/videos/crowd_sample.mp4", num_frames=1500):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, 25.0, (640, 360))
    
    np.random.seed(42)
    num_people = 16
    positions = np.random.randint(60, 300, size=(num_people, 2)).astype(float)
    velocities = np.random.uniform(-1.8, 1.8, size=(num_people, 2))
    
    for f in range(num_frames):
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        # Dark slate background
        frame[:] = (35, 35, 35)
        
        # Draw ground grid lines for perspective
        for y in range(0, 360, 40):
            cv2.line(frame, (0, y), (640, y), (45, 45, 45), 1)
        for x in range(0, 640, 40):
            cv2.line(frame, (x, 0), (x, 360), (45, 45, 45), 1)
            
        # Update positions
        positions += velocities
        for i in range(num_people):
            if positions[i, 0] < 40 or positions[i, 0] > 600:
                velocities[i, 0] *= -1
            if positions[i, 1] < 40 or positions[i, 1] > 320:
                velocities[i, 1] *= -1
                
            # Dynamic events throughout the video
            if f % 200 == 0:
                velocities[i] += np.random.uniform(-1.0, 1.0, size=2)
                
            x, y = int(positions[i, 0]), int(positions[i, 1])
            # Draw realistic person representation: Head circle + Body rect + outline
            cv2.circle(frame, (x, y - 12), 8, (240, 240, 240), -1)
            cv2.circle(frame, (x, y - 12), 8, (50, 50, 50), 1)
            cv2.ellipse(frame, (x, y + 10), (10, 18), 0, 0, 360, (200, 200, 200), -1)
            cv2.ellipse(frame, (x, y + 10), (10, 18), 0, 0, 360, (50, 50, 50), 1)
            
        out.write(frame)
        
    out.release()
    print(f"[OK] Generated rich crowd video: {output_path} ({num_frames} frames, ~{num_frames/25:.1f}s)")

if __name__ == "__main__":
    create_rich_crowd_video()

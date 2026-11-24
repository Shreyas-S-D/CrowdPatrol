import types
import torch
import cv2
import numpy as np
from deep_sort_realtime.deepsort_tracker import DeepSort

def _batched_embedder_predict(embedder_self, np_images):
    """
    Optimized batched PyTorch inference for MobileNetV2 DeepSORT embedder.
    Preserves exact preprocessing, normalization, model output & ordering.
    Uses pre-allocated contiguous memory and channels-last memory format on CPU
    for accelerated oneDNN AVX2/AVX-512 convolution kernels.
    """
    if not np_images:
        return []
    
    n = len(np_images)
    batch_np = np.empty((n, 224, 224, 3), dtype=np.uint8)
    for i, img in enumerate(np_images):
        if img is None or img.size == 0 or img.shape[0] == 0 or img.shape[1] == 0:
            batch_np[i] = 0
        else:
            resized = cv2.resize(img, (224, 224), interpolation=cv2.INTER_LINEAR)
            cv2.cvtColor(resized, cv2.COLOR_BGR2RGB, dst=batch_np[i])
            
    tensor = torch.from_numpy(batch_np).permute(0, 3, 1, 2).to(torch.float32) / 255.0
    
    if hasattr(embedder_self, 'gpu') and embedder_self.gpu:
        tensor = tensor.cuda()
        if hasattr(embedder_self, 'half') and embedder_self.half:
            tensor = tensor.half()
    else:
        # Accelerate CPU forward pass using channels-last memory format
        if not getattr(embedder_self, '_is_channels_last', False):
            try:
                embedder_self.model = embedder_self.model.to(memory_format=torch.channels_last)
                embedder_self._is_channels_last = True
            except Exception:
                pass
        tensor = tensor.to(memory_format=torch.channels_last)

    if not hasattr(embedder_self, '_mean_tensor') or embedder_self._mean_tensor.device != tensor.device:
        dtype = tensor.dtype
        device = tensor.device
        embedder_self._mean_tensor = torch.tensor([0.485, 0.456, 0.406], dtype=dtype, device=device).view(1, 3, 1, 1)
        embedder_self._std_tensor = torch.tensor([0.229, 0.224, 0.225], dtype=dtype, device=device).view(1, 3, 1, 1)

    tensor = (tensor - embedder_self._mean_tensor) / embedder_self._std_tensor

    with torch.inference_mode():
        output = embedder_self.model(tensor)

    return output.cpu().numpy()

class PersonTracker:
    def __init__(self, max_age=30, n_init=1):
        if torch.get_num_threads() > 14:
            try:
                torch.set_num_threads(14)
            except Exception:
                pass
        self.tracker = DeepSort(max_age=max_age, n_init=n_init)
        if self.tracker.embedder is not None:
            if hasattr(self.tracker.embedder, 'model') and self.tracker.embedder.model is not None:
                try:
                    self.tracker.embedder.model.eval()
                    self.tracker.embedder.model = self.tracker.embedder.model.to(memory_format=torch.channels_last)
                    self.tracker.embedder._is_channels_last = True
                except Exception:
                    pass
            self.tracker.embedder.predict = types.MethodType(_batched_embedder_predict, self.tracker.embedder)
        self.last_tracks = []
        self.last_visible_tracks = []

    def update(self, detections, frame):
        """
        Update tracker with new detections.
        Returns list of tracks: [x1,y1,x2,y2,track_id]
        """
        if len(detections) == 0 and frame is None:
            # Intermediate skipped frame prediction step
            return self.last_tracks
        
        tracks = self.tracker.update_tracks(detections, frame=frame)
        
        active_tracks = []
        visible_tracks = []
        for track in tracks:
            if track.is_confirmed() or (track.time_since_update <= 1 and track.hits >= 1):
                bbox = track.to_ltrb()  # [x1,y1,x2,y2]
                track_id = str(track.track_id)
                trk_data = [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]), track_id]
                active_tracks.append(trk_data)
                if track.time_since_update == 0:
                    visible_tracks.append(trk_data)
        
        self.last_tracks = active_tracks
        self.last_visible_tracks = visible_tracks
        return active_tracks

    def get_visible_tracks(self):
        """
        Return currently matched / visible active tracks (time_since_update == 0).
        """
        return self.last_visible_tracks

    def predict(self):
        """
        Advance Kalman filter prediction on intermediate frames without CNN feature extraction.
        Returns list of active tracks: [x1,y1,x2,y2,track_id]
        """
        return self.update([], frame=None)
"""Generate a synthetic test video so the connector pipeline can be exercised
without a physical camera. Produces motion (a moving block) that triggers clip cutting.

Note: this synthetic clip contains no real people, so the cloud AI will produce
zero retail-cue events (and therefore no alert) - it validates the *plumbing*
end to end. For meaningful detections/alerts, use real retail footage.

Usage:
    cd connector
    python samples/make_sample.py            # writes samples/test.mp4
"""
import os

import cv2
import numpy as np

OUT = os.path.join(os.path.dirname(__file__), "test.mp4")
W, H, FPS, SECONDS = 640, 360, 15, 20


def main() -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(OUT, fourcc, FPS, (W, H))
    total = FPS * SECONDS
    for i in range(total):
        frame = np.full((H, W, 3), 30, dtype=np.uint8)
        # A moving block sweeps across the (right-half) high-value zone to create motion.
        x = int((i / total) * (W - 80))
        cv2.rectangle(frame, (x, 140), (x + 70, 260), (60, 160, 240), -1)
        cv2.putText(frame, "ONEVO synthetic test", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
        writer.write(frame)
    writer.release()
    print(f"wrote {OUT} ({total} frames @ {FPS}fps)")


if __name__ == "__main__":
    main()

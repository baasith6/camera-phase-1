import torch
import torchvision.transforms as T
from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights
import cv2
import numpy as np

class ReIDExtractor:
    def __init__(self, device: str = "cpu"):
        self.device = device
        # Use MobileNet V3 small, dropping the final classifier layer for an embedding
        weights = MobileNet_V3_Small_Weights.DEFAULT
        self.model = mobilenet_v3_small(weights=weights)
        
        # We replace the classifier with Identity so it outputs the raw pooled features
        # MobileNetV3 small classifier has a Linear(576, 1024), Hardswish, Dropout, Linear(1024, 1000).
        # We can just remove it and take the output of the AdaptiveAvgPool2d (which gives 576-dim).
        self.model.classifier = torch.nn.Identity()
        
        self.model.to(self.device)
        self.model.eval()
        
        self.transform = T.Compose([
            T.ToPILImage(),
            T.Resize((256, 128)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    @torch.no_grad()
    def extract(self, frame, x, y, w, h) -> list[float]:
        """Extract a 576-dimensional embedding for a cropped bounding box.
        x, y, w, h are normalized coordinates (0..1) of the box.
        """
        img_h, img_w = frame.shape[:2]
        x1, y1 = max(0, int((x - w/2) * img_w)), max(0, int((y - h/2) * img_h))
        x2, y2 = min(img_w, int((x + w/2) * img_w)), min(img_h, int((y + h/2) * img_h))
        
        if x2 - x1 < 10 or y2 - y1 < 10:
            return []  # Too small

        crop = frame[y1:y2, x1:x2]
        # OpenCV is BGR, torchvision expects RGB
        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        
        img_t = self.transform(crop_rgb).unsqueeze(0).to(self.device)
        features = self.model(img_t)
        
        # Normalize the embedding to unit length (L2 normalization)
        features = torch.nn.functional.normalize(features, p=2, dim=1)
        
        return features[0].cpu().numpy().tolist()

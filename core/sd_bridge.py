import requests
import base64
import os
import logging
import json
from datetime import datetime
from pathlib import Path

# Setup logging
logger = logging.getLogger("UMBRA-SD")

class StableDiffusionBridge:
    def __init__(self, output_dir="data/visuals"):
        self.base_url = "http://127.0.0.1:7860"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def is_online(self):
        """Check if A1111 is running"""
        try:
            requests.get(f"{self.base_url}/sdapi/v1/progress", timeout=2)
            return True
        except:
            return False

    def get_image_description(self, image_base64):
        """
        Asks A1111 to describe the image (CLIP Interrogator).
        Returns a text description of what is actually in the image.
        """
        payload = {
            "image": image_base64,
            "model": "clip"
        }
        try:
            response = requests.post(f"{self.base_url}/sdapi/v1/interrogate", json=payload)
            return response.json().get("caption", "unknown")
        except Exception as e:
            logger.error(f"Interrogation failed: {e}")
            return "unknown"

    def generate(self, prompt, negative_prompt="ugly, blurred, low quality, watermark, text", width=512, height=512):
        """
        Generate an image and return both the path and the base64 (for analysis).
        """
        if not self.is_online():
            return None, None

        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "steps": 25,
            "width": width,
            "height": height,
            "cfg_scale": 7,
            "sampler_name": "Euler a"
        }

        try:
            response = requests.post(f"{self.base_url}/sdapi/v1/txt2img", json=payload)
            r = response.json()

            if 'images' not in r:
                return None, None

            img_base64 = r['images'][0]
            
            # Decode for saving
            image_data = base64.b64decode(img_base64)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"umbra_viz_{timestamp}.png"
            filepath = self.output_dir / filename
            
            with open(filepath, 'wb') as f:
                f.write(image_data)
            
            return str(filepath), img_base64
            
        except Exception as e:
            logger.error(f"SD Generation failed: {e}")
            return None, None
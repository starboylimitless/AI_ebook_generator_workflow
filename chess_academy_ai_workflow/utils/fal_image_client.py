import os
import requests
import fal_client
from pathlib import Path
from typing import Optional

class FalImageClient:
    """
    Client for interacting with Fal.ai API to generate images.
    Defaulting to 'flux/schnell' for cost-effective high quality.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("FAL_KEY")
        if self.api_key:
            os.environ["FAL_KEY"] = self.api_key

    def generate_image(self, prompt: str, model: str = "fal-ai/flux/schnell") -> str:
        """
        Generates an image via Fal.ai and returns the local path to the downloaded file.
        """
        if not self.api_key:
            raise ValueError("FAL_KEY is not set.")

        handler = fal_client.submit(
            model,
            arguments={
                "prompt": prompt,
                "image_size": "landscape_4_3",
                "num_inference_steps": 4,
                "enable_safety_checker": True
            }
        )
        
        result = handler.get()
        image_url = result["images"][0]["url"]
        
        # Download the image
        response = requests.get(image_url, stream=True)
        response.raise_for_status()
        
        # Save to a temporary location first, naming it by hash to avoid collisions
        temp_filename = f"fal_{abs(hash(prompt))}.png"
        temp_path = Path("generated_images") / temp_filename
        temp_path.parent.mkdir(exist_ok=True)
        
        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return str(temp_path.absolute())

# Dieses Programm wandelt alle Texturen in diesem Ordner zu Hintergrund-Texturen um.
# Hierfür wird das Bild dunkler gemacht.

from pathlib import Path
import os
from PIL import Image, ImageEnhance


directory = Path(__file__).parent.resolve()

def make_background_texture(image_path, output_path, brightness_factor=0.7):
    # Open the texture image
    img = Image.open(image_path).convert("RGBA")
    
    # Apply brightness reduction (0.3 means 30% of original brightness)
    enhancer = ImageEnhance.Brightness(img)
    dark_img = enhancer.enhance(brightness_factor)
    
    # Save the new background texture
    dark_img.save(output_path)

for file in os.scandir(directory):
    if file.name.endswith(".png"):
        print(file.path)
        make_background_texture(file.path, Path(directory) /  Path(f"background/{file.name}"), 0.3)
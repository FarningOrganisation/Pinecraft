# Dieses Programm wandelt alle Texturen in diesem Ordner zu Hintergrund-Texturen um.
# Hierfür wird das Bild dunkler gemacht.

from pathlib import Path
import os
from PIL import Image, ImageEnhance


directory = Path(__file__).parent.resolve()


count = 0
for file in os.scandir(directory):
    word_list = ["bottom", "top", "front", "back"]
    if file.name.endswith(".png"):
        for word in word_list:
            if word in file.name:
                os.remove(file.path)
                count += 1

print(f"{count} Dateien gelöscht")
        
        
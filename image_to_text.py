import pytesseract
from PIL import Image
import os

# Tesseract 설치 경로 (Windows)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

IMAGE_DIR = "output/images"
OCR_DIR = "output/ocr"

os.makedirs(OCR_DIR, exist_ok=True)

for filename in os.listdir(IMAGE_DIR):
    if not filename.endswith(".png"):
        continue

    image_path = os.path.join(IMAGE_DIR, filename)
    text_path = os.path.join(OCR_DIR, filename.replace(".png", ".txt"))

    img = Image.open(image_path)

    text = pytesseract.image_to_string(
        img,
        lang="kor+eng"
    )

    with open(text_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"OCR 완료: {filename}")

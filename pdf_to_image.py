from pdf2image import convert_from_path
import pytesseract
import re
import os

PDF_PATH = "input/animal.pdf"
OUTPUT_DIR = "output/image"
POPPLER_PATH = r"C:\Release-25.12.0-0\poppler-25.12.0\Library\bin"
os.makedirs(OUTPUT_DIR, exist_ok=True)


#. 특정 키워드 추출
KEYWORD_GROUPS = ["병력", "문진"]

def loose_match(text: str) -> bool:
    text = normalize(text)
    return (
        ("병력" in text or "병" in text) and
        ("문진" in text or "문" in text)
    )

def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text)

def get_candidate_regions(img):
    w, h = img.size
    return [
        # img.crop((0, 0, w, int(h * 0.4))),
        # img.crop((0, int(h * 0.3), w, int(h * 0.7))),
        img
    ]

def page_contains_keyword(img):
    regions = get_candidate_regions(img)
    
    for i, region in enumerate(regions):
        region = region.convert("L")
        text = pytesseract.image_to_string(
            region,
            lang="kor",
            config="--oem 1 --psm 6"
        )

        # print(f"[OCR] region {i}:", text[:50]) 

        if loose_match(text):
            return True
    return False

def loose_match(text: str) -> bool:
    text = normalize(text)
    return all(group in text for group in KEYWORD_GROUPS)

def find_target_pages(pdf_path, total_pages=300, dpi=300):
    pages = []

    for page in range(1, total_pages + 1):
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            first_page=page,
            last_page=page,
            poppler_path=POPPLER_PATH
        )
        img = images[0]

        if page_contains_keyword(img):
            pages.append(page)

        if page % 10 == 0:
            print(f"{page}페이지 처리 중...")

    return pages

pages = find_target_pages(PDF_PATH)
print("키워드 포함 페이지:", pages)


#

# pages = find_target_pages(PDF_PATH)

# for page in pages:
#     images = convert_from_path(
#         PDF_PATH,
#         dpi=300,
#         fmt="png",
#         first_page=page,
#         last_page=page,
#         poppler_path=POPPLER_PATH
#     )
#     images[0].save(f"{OUTPUT_DIR}/page_{page}.png", "PNG")
#     print(f"{page}페이지 저장 완료")


#. 특정 페이지만 추출

# PAGE_RANGES = [
#     (312, 323) #. 변환할 페이지
# ]
# for start, end in PAGE_RANGES:
#     for page in range(start, end + 1):
#         images = convert_from_path(
#             PDF_PATH,
#             dpi=300,
#             fmt="png",
#             poppler_path=POPPLER_PATH
#         ) 
#     images[0].save(f"{OUTPUT_DIR}/page_{page}.png", "PNG")
#     print(f"{page}페이지 변환 완료")

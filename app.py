from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
import easyocr
import cv2
import numpy as np
from pdf2image import convert_from_path
from reportlab.pdfgen import canvas
import os
import re
import zipfile
from PIL import Image
import shutil
import uuid

app = Flask(__name__)

# ================= CONFIG =================
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
POPPLER_PATH = r"D:\poppler\Library\bin"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

reader = easyocr.Reader(["en"], gpu=False)

# ================= HELPERS =================
def normalize(text):
    return re.sub(r"[^a-z0-9 ]", "", text.lower())

def get_text_color(img, x1, y1, x2, y2):
    try:
        sample = img[max(0, y1-5):y2, x1:x2]

        if sample.size == 0:
            return (0.1, 0.1, 0.1)

        avg = sample.mean(axis=(0, 1))

        r = avg[2] / 255
        g = avg[1] / 255
        b = avg[0] / 255

        # ===== brightness check =====
        brightness = (r + g + b) / 3

        if brightness > 0.6:
            return (0.2, 0.2, 0.2)   # dark gray (near black)

        elif brightness > 0.4:
            return (r * 0.7, g * 0.7, b * 0.7)

        else:
            return (r * 0.9, g * 0.9, b * 0.9)

    except:
        return (0.2, 0.2, 0.2)   # dark gray (near black)

# ================= OCR FUNCTION =================
def process_pdf(input_path, output_path, find_text, replace_text):
    
    # ✅ DPI reduced (important fix)
    pages = convert_from_path(input_path, dpi=150, poppler_path=POPPLER_PATH)
    
    c = canvas.Canvas(output_path)

    find_norm = normalize(find_text)
    find_clean = " ".join(find_norm.split())

    words = find_clean.split()
    find_list = set()

    find_list.add(find_clean)

    for i in range(len(words), 1, -1):
        find_list.add(" ".join(words[:i]))

    find_list.add("".join(words))

    if len(words) >= 2:
        find_list.add(words[0] + words[1])
        find_list.add(words[0] + " " + words[1])

    # ================= PROCESS EACH PAGE =================
    for page in pages:

        pil_image = page
        img = np.array(pil_image)

        # ================= 🔥 AUTO ROTATION =================
        h_img, w_img = img.shape[:2]

        if w_img > h_img:
            img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            pil_image = Image.fromarray(img)

        w, h = pil_image.size

        # ================= OCR =================
        results = reader.readtext(img, rotation_info=[90, 180, 270])

        # ================= PDF DRAW =================
        c.setPageSize((w, h))
        c.drawInlineImage(pil_image, 0, 0, width=w, height=h)

        # ================= TEXT REPLACE =================
        for bbox, text, prob in results:

            if not text:
                continue

            txt = normalize(text)
            txt_clean = " ".join(txt.split())
            txt_join = txt_clean.replace(" ", "")

            matched = False
            for f in find_list:
                if txt_clean == f or txt_join == f:
                    matched = True
                    break

            if not matched:
                continue

            x1 = int(bbox[0][0])
            y1 = int(bbox[0][1])
            x2 = int(bbox[2][0])
            y2 = int(bbox[2][1])

            pdf_y = h - y2
            width = x2 - x1
            height = y2 - y1

            # background clean
            c.setFillColorRGB(1, 1, 1)
            c.rect(x1, pdf_y, width, height, fill=1, stroke=0)

            # color match
            avg = img[y1:y2, x1:x2].mean(axis=(0, 1))
            r = avg[2] / 255
            g = avg[1] / 255
            b = avg[0] / 255
            c.setFillColorRGB(r, g, b)

            font_size = max(8, height * 0.8)
            text_y = pdf_y + (height * 0.15)

            c.setFont("Helvetica", font_size)
            c.drawString(x1 + 2, text_y, replace_text)

        # ================= NET DISBURSAL BLOCK =================
        for bbox, text, prob in results:
            txt = normalize(text)

            if "net disbursal" in txt:

                x_start = max(0, int(bbox[0][0]) - 110)
                y_start = max(0, int(bbox[0][1]) - 10)
                y_end = min(h, y_start + int(h * 0.5))  # 🔥 dynamic height

                pdf_y = h - y_end

                width = w - x_start
                height = y_end - y_start

                try:
                    sample = img[h-200:h-100, 20:120]
                    texture = cv2.resize(sample, (int(width), int(height)))
                    texture = cv2.GaussianBlur(texture, (7, 7), 0)

                    temp_texture = "texture.png"
                    cv2.imwrite(temp_texture, texture)

                    c.drawImage(temp_texture, x_start, pdf_y, width=width, height=height)

                except:
                    c.setFillColorRGB(0.95, 0.95, 0.95)
                    c.rect(x_start, pdf_y, width, height, fill=1, stroke=0)

        c.showPage()

    c.save()

# def process_pdf(input_path, output_path, find_text, replace_text):
#     pages = convert_from_path(input_path, dpi=300, poppler_path=POPPLER_PATH)
#     c = canvas.Canvas(output_path)

#     # ===== normalize input =====
#     find_norm = normalize(find_text)
#     find_clean = " ".join(find_norm.split())

#     # ================= 🔥 SMART FIND LIST =================
#     words = find_clean.split()
#     find_list = set()

#     # full phrase
#     find_list.add(find_clean)

#     # remove last words step-by-step
#     for i in range(len(words), 1, -1):
#         find_list.add(" ".join(words[:i]))

#     # no space version
#     find_list.add("".join(words))

#     # first 2 words variations
#     if len(words) >= 2:
#         find_list.add(words[0] + words[1])       # vishawasfinvest
#         find_list.add(words[0] + " " + words[1]) # vishawas finvest

#     # =====================================================

#     for page in pages:
#         pil_image = page
#         w, h = pil_image.size

#         img = np.array(pil_image)
#         results = reader.readtext(img)

#         c.setPageSize((w, h))
#         c.drawInlineImage(pil_image, 0, 0, width=w, height=h)

#         # ================= 1️⃣ TEXT REPLACE =================
#         for bbox, text, prob in results:

#             if not text:
#                 continue

#             txt = normalize(text)
#             txt_clean = " ".join(txt.split())
#             txt_join = txt_clean.replace(" ", "")

#             # 🔥 SMART MATCH CHECK
#             matched = False
#             for f in find_list:
#                 if txt_clean == f or txt_join == f:
#                     matched = True
#                     break

#             if not matched:
#                 continue

#             x1 = int(bbox[0][0])
#             y1 = int(bbox[0][1])
#             x2 = int(bbox[2][0])
#             y2 = int(bbox[2][1])

#             pdf_y = h - y2
#             width = x2 - x1
#             height = y2 - y1

#             # clean background
#             c.setFillColorRGB(1, 1, 1)
#             c.rect(x1, pdf_y, width, height, fill=1, stroke=0)

#             # color match
#             avg = img[y1:y2, x1:x2].mean(axis=(0, 1))
#             r = avg[2] / 255
#             g = avg[1] / 255
#             b = avg[0] / 255
#             c.setFillColorRGB(r, g, b)

#             # font
#             font_size = height * 0.8
#             text_y = pdf_y + (height * 0.15)

#             c.setFont("Helvetica", font_size)
#             c.drawString(x1 + 2, text_y, replace_text)

#         # ================= 2️⃣ NET DISBURSAL =================
#         for bbox, text, prob in results:
#             txt = normalize(text)

#             if "net disbursal" in txt:

#                 x_start = int(bbox[0][0]) - 110
#                 y_start = int(bbox[0][1]) - 10
#                 y_end = y_start + 550

#                 pdf_y = h - y_end

#                 width = w - x_start + 20
#                 height = y_end - y_start

#                 try:
#                     sample = img[h-200, 20:120]
#                     texture = cv2.resize(sample, (int(width), int(height)))
#                     texture = cv2.GaussianBlur(texture, (7, 7), 0)

#                     temp_texture = "texture.png"
#                     cv2.imwrite(temp_texture, texture)

#                     c.drawImage(temp_texture, x_start, pdf_y, width=width, height=height)

#                 except:
#                     c.setFillColorRGB(0.95, 0.95, 0.95)
#                     c.rect(x_start, pdf_y, width, height, fill=1, stroke=0)

#         c.showPage()

#     c.save()

# def process_pdf(input_path, output_path, find_text, replace_text):
#     pages = convert_from_path(input_path, dpi=300, poppler_path=POPPLER_PATH)
#     c = canvas.Canvas(output_path)

#     # ===== normalize input =====
#     find_norm = normalize(find_text)
#     find_clean = " ".join(find_norm.split())

#     # 🔥 auto variants
#     words = find_clean.split()
#     find_list = []
#     for i in range(len(words), 1, -1):
#         find_list.append(" ".join(words[:i]))

#     for page in pages:
#         pil_image = page
#         w, h = pil_image.size

#         img = np.array(pil_image)
#         results = reader.readtext(img)

#         c.setPageSize((w, h))
#         c.drawInlineImage(pil_image, 0, 0, width=w, height=h)

#         # ================= 1️⃣ TEXT REPLACE FIRST =================
#         for bbox, text, prob in results:

#             if not text:
#                 continue

#             txt = normalize(text)
#             txt_clean = " ".join(txt.split())

#             if txt_clean not in find_list:
#                 continue

#             x1 = int(bbox[0][0])
#             y1 = int(bbox[0][1])
#             x2 = int(bbox[2][0])
#             y2 = int(bbox[2][1])

#             pdf_y = h - y2
#             width = x2 - x1
#             height = y2 - y1

#             # clean
#             c.setFillColorRGB(1, 1, 1)
#             c.rect(x1, pdf_y, width, height, fill=1, stroke=0)

#             # color match
#             avg = img[y1:y2, x1:x2].mean(axis=(0, 1))
#             r = avg[2] / 255
#             g = avg[1] / 255
#             b = avg[0] / 255
#             c.setFillColorRGB(r, g, b)

#             # font
#             font_size = height * 0.8
#             text_y = pdf_y + (height * 0.15)

#             c.setFont("Helvetica", font_size)
#             c.drawString(x1 + 2, text_y, replace_text)

#         # ================= 2️⃣ NET DISBURSAL AFTER =================
#         for bbox, text, prob in results:
#                 txt = normalize(text)

#                 if "net disbursal" in txt:

#                     # right column start
#                     x_start = int(bbox[0][0]) - 110

#                     # 🔥 FULL HEIGHT (table + below section)
#                     y_start = int(bbox[0][1]) - 10
#                     y_end = y_start + 550   # adjust if needed (covers full section)

#                     pdf_y = h - y_end

#                     width = w - x_start + 20
#                     height = y_end - y_start

#                     # ================= COLOR MATCH =================
#                     # sample background color (average nearby area)
#                     #sample_x = x_start - 20
#                     #sample_y = y_start + 20
                    
#                     #c.setFillColorRGB(0.95, 0.95, 0.95) 
#                     # DRAW RECT 
#                     #c.rect(x_start, pdf_y, width, height, fill=1, stroke=0)
#                     # ===== PAPER TEXTURE FILL (REALISTIC) =====

#                     try:
#                         # clean background sample (bottom left area)
#                         sample = img[h-200, 20:120]
#                         # resize texture to match rectangle
#                         texture = cv2.resize(sample,(int(width), int(height)))
#                         texture = cv2.GaussianBlur(texture, (7, 7), 0)
                       
#                         temp_texture = "texture.png"
#                         cv2.imwrite(temp_texture, texture)

#                         # draw texture instead of grey color
#                         c.drawImage(temp_texture, x_start, pdf_y, width=width, height=height)

#                     except:
#                         # fallback (agar texture fail ho jaye)
#                         c.setFillColorRGB(0.95, 0.95, 0.95)
#                         c.rect(x_start, pdf_y, width, height, fill=1, stroke=0)

#         c.showPage()

#     c.save() 
# ================= FOLDER =================
def process_folder(input_folder, output_folder, find_text, replace_text, allowed):
    output_files = []

    for root, dirs, files in os.walk(input_folder):

        rel_path = os.path.relpath(root, input_folder)
        target_dir = os.path.join(output_folder, rel_path)
        os.makedirs(target_dir, exist_ok=True)

        for file_name in files:

            input_path = os.path.join(root, file_name)
            output_path = os.path.join(target_dir, file_name)

            if file_name.lower().endswith(".pdf"):

                if not allowed or file_name.lower().startswith(allowed):
                    process_pdf(input_path, output_path, find_text, replace_text)
                else:
                    shutil.copy2(input_path, output_path)

            else:
                shutil.copy2(input_path, output_path)

            # ✅ Store original name
            output_files.append((output_path, file_name))

    return output_files

# ================= ROUTE =================
@app.route("/", methods=["GET", "POST"])
def index():
    try:
        if request.method == "POST":

            find_text = request.form.get("find_text", "").lower()
            replace_text = request.form.get("replace_text", "")

            allowed_prefix = request.form.get("allowed_prefix", "")
            allowed = tuple([x.strip().lower() for x in allowed_prefix.split(",") if x.strip()])

            output_files = []

            # ===== SINGLE FILE =====
            files = request.files.getlist("files")

            for file in files:
                if file and file.filename:

                    unique_name = str(uuid.uuid4()) + "_" + file.filename

                    in_path = os.path.join(UPLOAD_FOLDER, unique_name)
                    out_path = os.path.join(OUTPUT_FOLDER, unique_name)

                    file.save(in_path)
                    process_pdf(in_path, out_path, find_text, replace_text)

                    # ✅ store original name
                    output_files.append((out_path, file.filename))

            # ===== FOLDER =====
            input_folder = request.form.get("input_folder")
            output_folder = request.form.get("output_folder")

            if input_folder and output_folder:
                output_files += process_folder(
                    input_folder,
                    output_folder,
                    find_text,
                    replace_text,
                    allowed
                )

            if not output_files:
                return jsonify({"error": "No files processed"}), 400

            # ===== ZIP =====
            zip_name = f"result_{uuid.uuid4()}.zip"
            zip_path = os.path.join(OUTPUT_FOLDER, zip_name)

            with zipfile.ZipFile(zip_path, "w") as z:
                for file_path, original_name in output_files:
                    z.write(file_path, original_name)

            return send_file(zip_path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return render_template("index.html")

# ================= MAIN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

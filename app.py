from flask import Flask, render_template, request, send_file
import easyocr
import cv2
import numpy as np
from pdf2image import convert_from_path
from reportlab.pdfgen import canvas
import os
import re
import zipfile

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
POPPLER_PATH = r"D:\poppler\Library\bin"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

reader = easyocr.Reader(["en"])

# ================= HELPERS =================


def normalize(text):
    return re.sub(r"[^a-z0-9 ]", "", text.lower())


# ================= CORE FUNCTION =================


def process_pdf(input_path, output_path, find_text, replace_text):
    pages = convert_from_path(input_path, dpi=300, poppler_path=POPPLER_PATH)
    c = canvas.Canvas(output_path)

    for page in pages:
     img = np.array(page)
     h, w, _ = img.shape

     results = reader.readtext(img)

     c.setPageSize((w, h))

     temp = "temp.png"
     cv2.imwrite(temp, img)
     c.drawImage(temp, 0, 0, width=w, height=h)

    for bbox, text, prob in results:
        if not text:
            continue

        txt = normalize(text)

        if find_text in txt:

            x1 = int(bbox[0][0])
            y1 = int(bbox[0][1])
            x2 = int(bbox[2][0])
            y2 = int(bbox[2][1])

            top_cut = 4 
            y1 += top_cut
            
            width = x2 - x1
            height = y2 - y1

            pdf_y = h - y2

            pad = 1
            x1 -= pad
            pdf_y -= pad
            width += pad * 2
            height += pad * 2

            # WHITE RECT
            c.setFillColorRGB(1, 1, 1)
            c.rect(x1, pdf_y, width, height, fill=1, stroke=0)

            # AUTO FIT TEXT
            font_size = height
            while font_size > 1:
                text_width = c.stringWidth(replace_text, "Helvetica-Bold", font_size)
                if text_width <= width:
                    break
                font_size -= 0.6

            text_y = pdf_y + (height - font_size) / 2

            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica-Bold", font_size)
            c.drawString(x1, text_y, replace_text)

    c.showPage()

    c.save()

# ================= ROUTE =================


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":

        files = request.files.getlist("files")
        find_text = request.form.get("find_text").lower()
        replace_text = request.form.get("replace_text")

        output_files = []

        for file in files:
            input_path = os.path.join(UPLOAD_FOLDER, file.filename)
            output_path = os.path.join(OUTPUT_FOLDER, "out_" + file.filename)

            file.save(input_path)

            process_pdf(input_path, output_path, find_text, replace_text)

            output_files.append(output_path)

        zip_path = os.path.join(OUTPUT_FOLDER, "result.zip")
        with zipfile.ZipFile(zip_path, "w") as z:
            for f in output_files:
                z.write(f, os.path.basename(f))

        return send_file(zip_path, as_attachment=True)

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)

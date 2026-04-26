import base64
import json
import re
import os
import cv2
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from openai import OpenAI
import config

client = OpenAI(api_key=config.OPENAI_API_KEY)

# ================= IMAGE OPTIMISATION =================

def compress_image(path):
    try:
        img = cv2.imread(path)
        if img is not None:
            cv2.imwrite(path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    except:
        pass

def preprocess_image(path):
    try:
        img = cv2.imread(path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        cv2.imwrite(path, gray)
    except:
        pass

def is_blurry(path):
    try:
        img = cv2.imread(path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.Laplacian(gray, cv2.CV_64F).var() < 100
    except:
        return False

def crop_text_zone(path):
    try:
        img = cv2.imread(path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            11, 2
        )

        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        boxes = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w > 100 and h > 30:
                boxes.append((x, y, w, h))

        if boxes:
            x, y, w, h = max(boxes, key=lambda b: b[2]*b[3])
            crop = img[y:y+h, x:x+w]
            new_path = path.replace(".jpg", "_crop.jpg")
            cv2.imwrite(new_path, crop)
            return new_path

    except:
        pass

    return path

# ================= VIN =================

def extract_vin_protocol(vin_grave_path, plaque_path, log):

    sources = [("VIN gravé", vin_grave_path), ("Plaque", plaque_path)]

    for name, path in sources:
        if not path:
            continue

        compress_image(path)
        preprocess_image(path)

        if is_blurry(path):
            log("⚠️ Image floue")

        path = crop_text_zone(path)

        log(f"🔍 VIN → {name}")

        try:
            with open(path, "rb") as f:
                img = base64.b64encode(f.read()).decode()

            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Retourne uniquement le VIN de 17 caractères"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}}
                    ]
                }]
            )

            raw = res.choices[0].message.content.strip()
            clean = re.sub(r'[^A-Z0-9]', '', raw.upper())

            if len(clean) == 17:
                log(f"✅ VIN : {clean}")
                return clean

        except Exception as e:
            log(f"⚠️ erreur {e}")

    return ""

# ================= PLAQUE =================

def extract_plaque_poids(plaque_path, log):

    if not plaque_path:
        return {}

    compress_image(plaque_path)
    preprocess_image(plaque_path)
    plaque_path = crop_text_zone(plaque_path)

    try:
        with open(plaque_path, "rb") as f:
            img = base64.b64encode(f.read()).decode()

        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": 'Retourne {"ptac":"","ptra":""}'},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}}
                ]
            }]
        )

        text = res.choices[0].message.content.replace("```", "")
        data = json.loads(text)

        return {
            "ptac": re.sub(r'\D', '', data.get("ptac", "")),
            "ptra": re.sub(r'\D', '', data.get("ptra", ""))
        }

    except:
        return {}

# ================= CARTE GRISE =================

def extract_carte_grise_protocol(path, log):

    compress_image(path)
    preprocess_image(path)
    path = crop_text_zone(path)

    try:
        with open(path, "rb") as f:
            img = base64.b64encode(f.read()).decode()

        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Retourne JSON carte grise"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}}
                ]
            }]
        )

        text = res.choices[0].message.content.replace("```", "")
        return json.loads(text)

    except:
        return {}

# ================= RAPPORT =================

def generate_report(cg_data, vin, poids, infos, imgs, log):

    doc = DocxTemplate("modele.docx")

    cg_data["vin_complet"] = vin if vin else "Non disponible"

    final = {**cg_data, **infos}

    for k, path in imgs.items():
        if path and os.path.exists(path):
            final[f"img_{k}"] = InlineImage(doc, path, height=Mm(45))

    doc.render(final)
    name = f"rapport_{infos.get('num_rapport','X')}.docx"
    doc.save(name)

    log(f"✔ Rapport généré : {name}")
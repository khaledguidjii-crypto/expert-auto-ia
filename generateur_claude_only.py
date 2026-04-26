import base64
import json
import re
import os
import cv2
from docxtpl import DocxTemplate
from openai import OpenAI

# 🔐 API depuis Render
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise Exception("API KEY MANQUANTE")

client = OpenAI(api_key=api_key)

# ================= IMAGE =================

def compress_image(path):
    try:
        img = cv2.imread(path)
        if img is not None:
            img = cv2.resize(img, (800, 600))  # optimisation mémoire
            cv2.imwrite(path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
    except:
        pass

# ================= VIN =================

def extract_vin_protocol(vin_path, plaque_path, log):

    for path in [vin_path, plaque_path]:

        if not path:
            continue

        compress_image(path)

        try:
            with open(path, "rb") as f:
                img = base64.b64encode(f.read()).decode()

            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Donne uniquement un VIN valide de 17 caractères"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}}
                    ]
                }]
            )

            txt = res.choices[0].message.content
            vin = re.sub(r'[^A-Z0-9]', '', txt.upper())

            if len(vin) == 17:
                log(f"VIN trouvé: {vin}")
                return vin

        except Exception as e:
            log(f"Erreur VIN: {e}")

    return ""

# ================= CARTE =================

def extract_carte_grise_protocol(path, log):

    compress_image(path)

    try:
        with open(path, "rb") as f:
            img = base64.b64encode(f.read()).decode()

        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Retourne uniquement un JSON propre des infos carte grise"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}}
                ]
            }]
        )

        txt = res.choices[0].message.content.replace("```", "")

        try:
            return json.loads(txt)
        except:
            log("⚠️ JSON invalide IA")
            return {}

    except Exception as e:
        log(f"Erreur carte: {e}")
        return {}

# ================= PLAQUE =================

def extract_plaque_poids(path, log):
    return {}

# ================= RAPPORT =================

def generate_report(cg, vin, poids, infos, imgs, log):

    base = os.path.dirname(os.path.abspath(__file__))
    template = os.path.join(base, "modele.docx")

    if not os.path.exists(template):
        raise Exception("modele.docx manquant")

    doc = DocxTemplate(template)

    # Ajout VIN
    cg["vin"] = vin if vin else "NON TROUVÉ"

    # Générer nom dynamique
    filename = f"rapport_{infos.get('num_rapport','WEB001')}.docx"
    output_path = os.path.join(base, filename)

    doc.render(cg)
    doc.save(output_path)

    log(f"✔ rapport généré : {output_path}")

    return output_path
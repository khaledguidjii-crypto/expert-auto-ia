from flask import Flask, render_template, request, send_file
import os

# 🔥 IMPORT TON CODE PRINCIPAL
from generateur_claude_only import (
    extract_carte_grise_protocol,
    extract_vin_protocol,
    extract_plaque_poids,
    generate_report
)

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= PAGE =================
@app.route("/")
def index():
    return render_template("index.html")

# ================= UPLOAD =================
@app.route("/upload", methods=["POST"])
def upload():

    try:
        carte = request.files.get("carte")
        vin = request.files.get("vin")
        plaque = request.files.get("plaque")
        vehicule = request.files.get("vehicule")

        # 🔥 sauvegarde fichiers
        carte_path = os.path.join(UPLOAD_FOLDER, carte.filename) if carte else None
        vin_path = os.path.join(UPLOAD_FOLDER, vin.filename) if vin else None
        plaque_path = os.path.join(UPLOAD_FOLDER, plaque.filename) if plaque else None
        vehicule_path = os.path.join(UPLOAD_FOLDER, vehicule.filename) if vehicule else None

        if carte:
            carte.save(carte_path)
        if vin:
            vin.save(vin_path)
        if plaque:
            plaque.save(plaque_path)
        if vehicule:
            vehicule.save(vehicule_path)

        print("📂 fichiers sauvegardés")

        # ================= IA =================
        def log(msg):
            print(msg)

        cg_data = extract_carte_grise_protocol(carte_path, log)
        vin_data = extract_vin_protocol(vin_path, plaque_path, log)
        poids = extract_plaque_poids(plaque_path, log)

        # infos supplémentaires
        infos = {
            "num_rapport": "WEB001",
            "nom_proprietaire": "Client Web"
        }

        imgs = {
            "carte": carte_path,
            "vin": vin_path,
            "plaque": plaque_path,
            "vehicule": vehicule_path
        }

        # 🔥 génération rapport
        generate_report(cg_data, vin_data, poids, infos, imgs, log)

        rapport_path = os.path.abspath(f"rapport_{infos['num_rapport']}.docx")

        print("📄 rapport généré :", rapport_path)

        return send_file(rapport_path, as_attachment=True)

    except Exception as e:
        print("❌ ERREUR :", e)
        return f"Erreur serveur : {e}"


# ================= RUN =================
if __name__ == "__main__":
    # 🔥 IMPORTANT pour téléphone
    app.run(host="0.0.0.0", port=5000, debug=True)
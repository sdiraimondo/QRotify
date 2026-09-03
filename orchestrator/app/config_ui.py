from flask import Blueprint, request, jsonify, render_template_string
import json
import os

config_bp = Blueprint("config", __name__)

CONFIG_PATH = os.environ.get("CONFIG_STORE", "/data/config.json")

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {"device_id": None, "device_name": None}

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f)

PAGE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>QRotify - Configuration</title>
  <style>
    body { font-family: sans-serif; max-width: 500px; margin: 40px auto; }
    select, button { font-size: 1.1em; padding: 8px; width: 100%; margin-top: 10px; }
    .current { background: #eef; padding: 10px; border-radius: 6px; margin-bottom: 20px; }
  </style>
</head>
<body>
  <h1>🎵 QRotify - Config</h1>
  <div class="current">
    Device actuel : <strong>{{ current_name or "Aucun" }}</strong>
  </div>
  <form method="post" action="/config/device">
    <label>Choisir l'enceinte cible :</label>
    <select name="device_id">
      {% for d in devices %}
        <option value="{{ d.id }}" data-name="{{ d.name }}"
          {% if d.id == current_id %}selected{% endif %}>
          {{ d.name }} ({{ d.type }})
        </option>
      {% endfor %}
    </select>
    <button type="submit">Enregistrer</button>
  </form>
  <p><a href="/">🔄 Rafraîchir la liste</a></p>
</body>
</html>
"""

@config_bp.route("/", methods=["GET"])
def index():
    from spotify_client import get_available_devices  # ta fonction existante
    devices = get_available_devices()
    cfg = load_config()
    return render_template_string(
        PAGE,
        devices=devices,
        current_id=cfg.get("device_id"),
        current_name=cfg.get("device_name"),
    )

@config_bp.route("/config/device", methods=["POST"])
def set_device():
    from spotify_client import get_available_devices
    device_id = request.form["device_id"]
    devices = get_available_devices()
    match = next((d for d in devices if d["id"] == device_id), None)
    cfg = {
        "device_id": device_id,
        "device_name": match["name"] if match else device_id,
    }
    save_config(cfg)
    return f"<p>✅ Device enregistré : {cfg['device_name']}. <a href='/'>Retour</a></p>"

@config_bp.route("/api/devices", methods=["GET"])
def api_devices():
    from spotify_client import get_available_devices
    return jsonify(get_available_devices())

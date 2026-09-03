"""API Flask QRotify: authentification Spotify et lancement sur librespot."""
from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

import spotipy
from flask import Flask, jsonify, redirect, request
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyOAuth
from config_ui import config_bp

app = Flask(__name__)
app.register_blueprint(config_bp)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [orchestrator] %(message)s",
)
LOG = logging.getLogger("qrotify.orchestrator")
app = Flask(__name__)

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "")
DEVICE_NAME = os.getenv("LIBRESPOT_DEVICE_NAME", "QRotify")
TOKEN_STORE = os.getenv("TOKEN_STORE", "/data/spotify-cache.json")
SCOPE = "user-read-playback-state user-modify-playback-state user-read-currently-playing"


def oauth_manager() -> SpotifyOAuth:
    """Construit le gestionnaire OAuth; le cache est conservé entre redémarrages."""
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        raise RuntimeError("SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET et SPOTIFY_REDIRECT_URI sont requis")
    parent = os.path.dirname(TOKEN_STORE)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_handler=CacheFileHandler(cache_path=TOKEN_STORE),
        open_browser=False,
    )


def spotify_client() -> spotipy.Spotify:
    manager = oauth_manager()
    token = manager.get_cached_token()
    if not token:
        raise RuntimeError("Authentification Spotify absente: ouvrez /login")
    return spotipy.Spotify(auth_manager=manager)


def extract_uri(value: str) -> str | None:
    """Accepte spotify:type:id ou une URL open.spotify.com/type/id?query."""
    value = (value or "").strip()
    if value.startswith("spotify:"):
        parts = value.split(":")
        if len(parts) == 3 and parts[1] in {"album", "track", "playlist"} and parts[2]:
            return f"spotify:{parts[1]}:{parts[2]}"
        return None
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc.lower() in {"open.spotify.com", "www.open.spotify.com"}:
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] in {"album", "track", "playlist"} and parts[1]:
            return f"spotify:{parts[0]}:{parts[1]}"
    return None


def find_device_id(client: spotipy.Spotify) -> str | None:
    """Cherche le device librespot configuré, sans supposer qu'il soit actif."""
    devices = client.devices().get("devices", [])
    expected = DEVICE_NAME.casefold().strip()
    exact = next((d for d in devices if d.get("name", "").casefold() == expected), None)
    candidate = exact or next((d for d in devices if expected in d.get("name", "").casefold()), None)
    if candidate:
        LOG.info("Device Spotify sélectionné: %s (%s)", candidate.get("name"), candidate.get("id"))
        return candidate.get("id")
    LOG.error("Device librespot introuvable (nom configuré: %s); devices: %s", DEVICE_NAME, [d.get("name") for d in devices])
    return None


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "orchestrator"})


@app.get("/login")
def login():
    try:
        return redirect(oauth_manager().get_authorize_url())
    except Exception as exc:
        LOG.exception("Impossible de préparer la connexion Spotify")
        return jsonify(error=str(exc)), 500


@app.get("/callback")
def callback():
    try:
        if request.args.get("error"):
            return jsonify(error=request.args["error"]), 400
        code = request.args.get("code")
        if not code:
            return jsonify(error="Paramètre code manquant"), 400
        oauth_manager().get_access_token(code, as_dict=True, check_cache=False)
        return "Authentification Spotify réussie. Vous pouvez fermer cette page.\n"
    except Exception as exc:
        LOG.exception("Échec du callback Spotify")
        return jsonify(error=str(exc)), 500


@app.post("/play")
def play():
    body = request.get_json(silent=True) or {}
    uri = extract_uri(body.get("uri", ""))
    if not uri:
        return jsonify(error="uri Spotify album/track/playlist invalide"), 400
    try:
        client = spotify_client()
        device_id = find_device_id(client)
        if not device_id:
            return jsonify(error=f"Device librespot '{DEVICE_NAME}' introuvable"), 503
        client.start_playback(device_id=device_id, context_uri=uri)
        LOG.info("Lecture démarrée: %s sur %s", uri, DEVICE_NAME)
        return jsonify(status="playing", uri=uri, device=DEVICE_NAME)
    except spotipy.SpotifyException as exc:
        LOG.exception("Erreur Spotify lors de la lecture")
        return jsonify(error=f"Erreur Spotify: {exc}"), 502
    except Exception as exc:
        LOG.exception("Erreur interne lors de la lecture")
        return jsonify(error=str(exc)), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888)

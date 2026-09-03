"""Lecteur QR continu pour QRotify.

Le conteneur doit avoir accès à la webcam (par exemple /dev/video0) et à
l'URL interne de l'orchestrateur. Les paramètres sont configurables par
variables d'environnement afin de rester utilisable dans Docker Compose.
"""
from __future__ import annotations

import logging
import os
import time
from urllib.parse import urlparse

import cv2
import requests
from pyzbar.pyzbar import decode

LOG = logging.getLogger("qrotify.qr-reader")
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [qr-reader] %(message)s",
)

CAMERA_DEVICE = os.getenv("CAMERA_DEVICE", "/dev/video0")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8888").rstrip("/")
DEBOUNCE_SECONDS = float(os.getenv("DEBOUNCE_SECONDS", "8"))
RETRY_COUNT = int(os.getenv("RETRY_COUNT", "3"))
RETRY_DELAY = float(os.getenv("RETRY_DELAY", "1.5"))


def extract_spotify_uri(raw: str) -> str | None:
    """Retourne une URI Spotify album/track/playlist, ou None si invalide."""
    value = raw.strip()
    if value.startswith("spotify:"):
        parts = value.split(":")
        if len(parts) == 3 and parts[1] in {"album", "track", "playlist"} and parts[2]:
            return f"spotify:{parts[1]}:{parts[2]}"
        return None

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {
        "open.spotify.com", "www.open.spotify.com"
    }:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] in {"album", "track", "playlist"} and parts[1]:
        # L'identifiant Spotify ne contient normalement pas de slash; on
        # ignore les segments ultérieurs et les paramètres de tracking.
        return f"spotify:{parts[0]}:{parts[1]}"
    return None


def send_to_orchestrator(uri: str) -> bool:
    """POST le code décodé, avec quelques tentatives en cas d'erreur réseau."""
    endpoint = f"{ORCHESTRATOR_URL}/play"
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            response = requests.post(endpoint, json={"uri": uri}, timeout=8)
            if response.ok:
                LOG.info("Lecture demandée pour %s", uri)
                return True
            LOG.warning("Orchestrateur %s (%s/%s): %s", response.status_code, attempt, RETRY_COUNT, response.text[:300])
        except requests.RequestException as exc:
            LOG.warning("Échec POST vers %s (%s/%s): %s", endpoint, attempt, RETRY_COUNT, exc)
        if attempt < RETRY_COUNT:
            time.sleep(RETRY_DELAY * attempt)
    LOG.error("Impossible d'envoyer %s après %s tentative(s)", uri, RETRY_COUNT)
    return False


def open_camera() -> cv2.VideoCapture:
    """Ouvre la webcam et lève une erreur explicite si elle n'est pas disponible."""
    camera = cv2.VideoCapture(CAMERA_DEVICE, cv2.CAP_V4L2)
    if not camera.isOpened():
        camera.release()
        raise RuntimeError(f"Impossible d'ouvrir la webcam {CAMERA_DEVICE}")
    return camera


def main() -> None:
    last_uri: str | None = None
    last_sent_at = 0.0
    while True:
        camera = None
        try:
            camera = open_camera()
            LOG.info("Webcam ouverte: %s; orchestrateur: %s", CAMERA_DEVICE, ORCHESTRATOR_URL)
            while True:
                ok, frame = camera.read()
                if not ok:
                    raise RuntimeError("La webcam n'a pas fourni d'image")
                for symbol in decode(frame):
                    try:
                        raw = symbol.data.decode("utf-8").strip()
                    except UnicodeDecodeError:
                        LOG.warning("QR ignoré: contenu non UTF-8")
                        continue
                    uri = extract_spotify_uri(raw)
                    if not uri:
                        LOG.info("QR ignoré (pas une URL/URI Spotify supportée): %s", raw[:160])
                        continue
                    now = time.monotonic()
                    if uri == last_uri and now - last_sent_at < DEBOUNCE_SECONDS:
                        LOG.debug("QR identique ignoré pendant l'anti-rebond: %s", uri)
                        continue
                    if send_to_orchestrator(uri):
                        last_uri, last_sent_at = uri, now
                # Pas d'affichage GUI dans un conteneur headless.
                time.sleep(0.05)
        except (RuntimeError, cv2.error) as exc:
            LOG.error("Lecteur QR en erreur: %s; nouvelle tentative dans 5 s", exc)
            time.sleep(5)
        except Exception:
            LOG.exception("Erreur inattendue dans la boucle du lecteur; reprise dans 5 s")
            time.sleep(5)
        finally:
            if camera is not None:
                camera.release()


if __name__ == "__main__":
    main()

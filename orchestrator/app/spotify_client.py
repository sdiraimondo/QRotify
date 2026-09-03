import requests
from token_store import get_valid_token  # ta gestion de refresh token existante

def get_available_devices():
    token = get_valid_token()
    resp = requests.get(
        "https://api.spotify.com/v1/me/player/devices",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()["devices"]


def play_album_on_device(album_uri, device_id=None):
    token = get_valid_token()
    if device_id is None:
        cfg = load_config()  # importé depuis config_ui
        device_id = cfg.get("device_id")
    if not device_id:
        raise ValueError("Aucun device configuré")

    resp = requests.put(
        f"https://api.spotify.com/v1/me/player/play?device_id={device_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"context_uri": album_uri},
    )
    resp.raise_for_status()

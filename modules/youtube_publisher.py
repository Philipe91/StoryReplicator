"""
v6.4 — Agente Publicador: upload automático no YouTube (Data API v3, grátis).

Setup (1x, gratuito):
  1. console.cloud.google.com → criar projeto → ativar "YouTube Data API v3"
  2. Tela de consentimento OAuth (External, modo teste, seu e-mail)
  3. Credenciais → OAuth Client ID → tipo "Desktop app"
  4. Baixar o JSON como `client_secrets.json` na raiz do projeto
  5. pip install google-api-python-client google-auth-oauthlib
  6. Primeiro upload abre o navegador para autorizar (token salvo em
     youtube_token.json — os próximos são 100% automáticos)

Quota gratuita: 10.000 unidades/dia; 1 upload = 1.600 → ~6 uploads/dia.

Uso:
  python -m modules.youtube_publisher output/copa_2026            (privado)
  python -m modules.youtube_publisher output/copa_2026 --publico
  python -m modules.youtube_publisher output/copa_2026 --agendar "2026-07-10T18:00"
"""

import json
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
ROOT = Path(__file__).resolve().parents[1]


def available() -> bool:
    try:
        import googleapiclient  # noqa: F401
        import google_auth_oauthlib  # noqa: F401
        return (ROOT / "client_secrets.json").exists()
    except ImportError:
        return False


def _get_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token_path = ROOT / "youtube_token.json"
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(ROOT / "client_secrets.json"), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def publish(output_dir, privacy: str = "private",
            publish_at: str = None) -> dict:
    """
    Sobe o vídeo de uma pasta de saída do pipeline usando os metadados do
    agente SEO (14_metadata.json) + thumbnail. Retorna {video_id, url}.
    privacy: private | unlisted | public. publish_at: ISO 8601 (agenda).
    """
    from googleapiclient.http import MediaFileUpload

    out = Path(output_dir)
    video = out / "final_video.mp4"
    if not video.exists():
        raise FileNotFoundError(f"{video} não existe")

    md = {}
    md_file = out / "14_metadata.json"
    if md_file.exists():
        md = json.loads(md_file.read_text(encoding="utf-8"))

    title = (md.get("titulos", {}).get("youtube_shorts")
             or md.get("titulos", {}).get("youtube") or video.stem)[:100]
    description = (md.get("descricao", {}) or {}).get("completa", "")[:4900]
    tags = (md.get("tags_youtube") or [])[:30]

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "27",          # Education
            "defaultLanguage": "pt-BR",
            "defaultAudioLanguage": "pt-BR",
        },
        "status": {
            "privacyStatus": "private" if publish_at else privacy,
            "selfDeclaredMadeForKids": False,
            # Transparência: narração/algumas imagens são sintéticas
            "containsSyntheticMedia": True,
        },
    }
    if publish_at:
        body["status"]["publishAt"] = publish_at

    yt = _get_service()
    media = MediaFileUpload(str(video), chunksize=8 * 1024 * 1024,
                            resumable=True, mimetype="video/mp4")
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  upload: {int(status.progress() * 100)}%")
    video_id = response["id"]
    print(f"  Vídeo no ar (id={video_id})")

    thumb = out / "thumbnail.jpg"
    if thumb.exists():
        try:
            yt.thumbnails().set(videoId=video_id,
                                media_body=MediaFileUpload(str(thumb))).execute()
            print("  Thumbnail aplicada")
        except Exception as e:
            print(f"  [thumb] {e} (canal precisa de verificação p/ thumb custom)")

    result = {"video_id": video_id,
              "url": f"https://youtu.be/{video_id}",
              "title": title, "privacy": body["status"]["privacyStatus"],
              "publish_at": publish_at}
    (out / "youtube_upload.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Upload de vídeo do pipeline p/ YouTube")
    p.add_argument("output_dir")
    p.add_argument("--publico", action="store_true")
    p.add_argument("--nao-listado", action="store_true")
    p.add_argument("--agendar", default=None, help="ISO 8601, ex 2026-07-10T18:00:00-03:00")
    a = p.parse_args()
    privacy = "public" if a.publico else ("unlisted" if a.nao_listado else "private")
    r = publish(a.output_dir, privacy=privacy, publish_at=a.agendar)
    print(json.dumps(r, ensure_ascii=False, indent=2))

"""Google API authentication utilities."""

import os
from typing import Any

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/presentations"]


def get_slides_service_oauth(
    client_secret_path: str, token_path: str = "token.json"
) -> Any:
    """Get authenticated Slides API service using OAuth.

    Args:
        client_secret_path: Path to OAuth client secret JSON file.
        token_path: Path to store/retrieve cached OAuth token.

    Returns:
        Google Slides API service resource.
    """
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("slides", "v1", credentials=creds)


def get_slides_service_sa(sa_json_path: str) -> Any:
    """Get authenticated Slides API service using service account.

    Args:
        sa_json_path: Path to service account JSON key file.

    Returns:
        Google Slides API service resource.
    """
    creds = service_account.Credentials.from_service_account_file(
        sa_json_path, scopes=SCOPES
    )
    return build("slides", "v1", credentials=creds)

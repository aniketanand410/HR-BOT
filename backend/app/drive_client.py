"""Google Drive traversal from a root folder (supports nested HR/... layout)."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Iterator

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ("https://www.googleapis.com/auth/drive.readonly",)

# MIME types we can ingest as binary downloads
BINARY_MIMES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
)

# Google Workspace files → export format (binary)
EXPORT_MIMES = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
}


@dataclass(frozen=True)
class DriveFile:
    file_id: str
    name: str
    mime_type: str
    logical_path: str  # e.g. HR/policies/Handbook.pdf


def _service(credentials_path: str):
    creds = service_account.Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def iter_files_recursive(credentials_path: str, root_folder_id: str) -> Iterator[DriveFile]:
    """Walk Drive starting at root_folder_id; yields files with a stable logical_path."""
    service = _service(credentials_path)

    def list_children(folder_id: str) -> list[dict]:
        q = f"'{folder_id}' in parents and trashed = false"
        items: list[dict] = []
        page_token = None
        while True:
            resp = (
                service.files()
                .list(
                    q=q,
                    fields="nextPageToken, files(id, name, mimeType)",
                    pageToken=page_token,
                    pageSize=200,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            items.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return items

    # BFS: (folder_id, path_prefix)
    queue: list[tuple[str, str]] = [(root_folder_id, "")]
    while queue:
        folder_id, prefix = queue.pop(0)
        for f in list_children(folder_id):
            fid = f["id"]
            name = f["name"]
            mime = f.get("mimeType", "")
            path = f"{prefix}/{name}" if prefix else name

            if mime == "application/vnd.google-apps.folder":
                queue.append((fid, path))
                continue

            if mime in BINARY_MIMES or mime in EXPORT_MIMES:
                yield DriveFile(file_id=fid, name=name, mime_type=mime, logical_path=path)


def download_file_bytes(credentials_path: str, drive_file: DriveFile) -> tuple[bytes, str]:
    """Return (content_bytes, filename_suffix_for_parser)."""
    service = _service(credentials_path)

    if drive_file.mime_type in EXPORT_MIMES:
        export_mime, suffix = EXPORT_MIMES[drive_file.mime_type]
        request = service.files().export_media(fileId=drive_file.file_id, mimeType=export_mime)
    else:
        suffix = ".pdf" if drive_file.mime_type == "application/pdf" else ""
        if drive_file.mime_type.endswith("wordprocessingml.document"):
            suffix = ".docx"
        elif drive_file.mime_type.endswith("presentationml.presentation"):
            suffix = ".pptx"
        request = service.files().get_media(fileId=drive_file.file_id, supportsAllDrives=True)

    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue(), suffix

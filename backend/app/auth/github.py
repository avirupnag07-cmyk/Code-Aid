"""Small GitHub OAuth authorization-code integration.

OAuth tokens are held only in the process memory session map.  They are never
returned by an endpoint or written to SQLite/source metadata.  Public Git
imports do not require this integration; it exists so a configured deployment
can establish and disconnect a GitHub session without claiming auth support
when the credentials are absent.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException, Request as FastAPIRequest
from fastapi.responses import RedirectResponse

from ..config import Settings


class GitHubOAuth:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._sessions: Dict[str, tuple[str, float]] = {}
        self._cookie_secret = (settings.oauth_cookie_secret or secrets.token_urlsafe(32)).encode("utf-8")

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.github_client_id
            and self.settings.github_client_secret
            and self.settings.github_redirect_uri
        )

    def status(self, request: FastAPIRequest) -> Dict[str, object]:
        session_id = self._read_timed_cookie(request.cookies.get("code_aid_github_session"))
        return {
            "provider": "github",
            "configured": self.configured,
            "connected": bool(self.token_for_request(request)),
            "message": "configured" if self.configured else "GitHub OAuth is not configured",
        }

    @staticmethod
    def _encode(value: str) -> str:
        return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")

    @staticmethod
    def _decode(value: str) -> Optional[str]:
        try:
            padding = "=" * (-len(value) % 4)
            return base64.urlsafe_b64decode((value + padding).encode("ascii")).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None

    def _signed_cookie(self, payload: str) -> str:
        encoded = self._encode(payload)
        signature = hmac.new(self._cookie_secret, encoded.encode("ascii"), hashlib.sha256).digest()
        return encoded + "." + self._encode(signature.hex())

    def _read_cookie(self, value: Optional[str]) -> Optional[str]:
        if not value or "." not in value:
            return None
        encoded, signature = value.rsplit(".", 1)
        expected = hmac.new(self._cookie_secret, encoded.encode("ascii"), hashlib.sha256).digest()
        decoded_signature = self._decode(signature)
        if not decoded_signature:
            return None
        try:
            valid = hmac.compare_digest(expected.hex(), decoded_signature)
        except TypeError:
            valid = False
        if not valid:
            return None
        return self._decode(encoded)

    def _cookie_payload(self, value: str) -> str:
        return json.dumps({"value": value, "expires": int(time.time()) + 600}, separators=(",", ":"))

    def _read_timed_cookie(self, value: Optional[str]) -> Optional[str]:
        decoded = self._read_cookie(value)
        if not decoded:
            return None
        try:
            payload = json.loads(decoded)
            if int(payload.get("expires", 0)) < int(time.time()):
                return None
            result = payload.get("value")
            return result if isinstance(result, str) else None
        except (TypeError, ValueError):
            return None

    def _secure_cookie(self) -> bool:
        return bool(self.settings.github_redirect_uri and self.settings.github_redirect_uri.startswith("https://"))

    def start(self) -> RedirectResponse:
        if not self.configured:
            raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
        query = urlencode(
            {
                "client_id": self.settings.github_client_id,
                "redirect_uri": self.settings.github_redirect_uri,
                "response_type": "code",
                # GitHub OAuth Apps expose private repository read access via
                # `repo`; the integration never requests write operations.
                "scope": "read:user repo",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        response = RedirectResponse("https://github.com/login/oauth/authorize?" + query, status_code=307)
        cookie_options = {"httponly": True, "secure": self._secure_cookie(), "samesite": "lax", "max_age": 600, "path": "/"}
        response.set_cookie("code_aid_github_state", self._signed_cookie(self._cookie_payload(state)), **cookie_options)
        response.set_cookie("code_aid_github_pkce", self._signed_cookie(self._cookie_payload(verifier)), **cookie_options)
        return response

    def _exchange(self, code: str, verifier: str) -> str:
        payload = urlencode(
            {
                "client_id": self.settings.github_client_id,
                "client_secret": self.settings.github_client_secret,
                "code": code,
                "redirect_uri": self.settings.github_redirect_uri,
                "code_verifier": verifier,
            }
        ).encode("ascii")
        request = Request(
            "https://github.com/login/oauth/access_token",
            data=payload,
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read(64 * 1024).decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=502, detail="GitHub token exchange failed") from exc
        token = data.get("access_token") if isinstance(data, dict) else None
        if not isinstance(token, str) or not token:
            raise HTTPException(status_code=502, detail="GitHub token exchange failed")
        return token

    def callback(self, request: FastAPIRequest, code: Optional[str], state: Optional[str]) -> Dict[str, object]:
        if not self.configured:
            raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")
        expected_state = self._read_timed_cookie(request.cookies.get("code_aid_github_state"))
        verifier = self._read_timed_cookie(request.cookies.get("code_aid_github_pkce"))
        if not code or not state or not expected_state or not verifier or not hmac.compare_digest(state, expected_state):
            raise HTTPException(status_code=400, detail="Invalid GitHub OAuth state")
        token = self._exchange(code, verifier)
        session_id = secrets.token_urlsafe(32)
        self._sessions[session_id] = (token, time.time() + 3600)
        response = {"provider": "github", "connected": True}
        # The route wraps this result with a response so cookies can be set.
        request.state.github_session_cookie = self._signed_cookie(self._cookie_payload(session_id))
        return response

    def disconnect(self, request: FastAPIRequest) -> Dict[str, object]:
        session_id = self._read_timed_cookie(request.cookies.get("code_aid_github_session"))
        if session_id:
            self._sessions.pop(session_id, None)
        return {"provider": "github", "connected": False}

    def token_for_request(self, request: FastAPIRequest) -> Optional[str]:
        session_id = self._read_timed_cookie(request.cookies.get("code_aid_github_session"))
        if not session_id:
            return None
        session = self._sessions.get(session_id)
        if not session:
            return None
        token, expires_at = session
        if expires_at <= time.time():
            self._sessions.pop(session_id, None)
            return None
        return token

    def _api(self, token: str, path: str) -> object:
        request = Request(
            "https://api.github.com{}".format(path),
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer {}".format(token),
                "User-Agent": "Code-Aid/0.1",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read(512 * 1024).decode("utf-8"))
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise HTTPException(status_code=401, detail="GitHub authorization is expired or insufficient") from exc
            if exc.code == 404:
                raise HTTPException(status_code=404, detail="GitHub repository was not found or is not accessible") from exc
            raise HTTPException(status_code=502, detail="GitHub API request failed") from exc
        except (URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=502, detail="GitHub API request failed") from exc

    def repositories(self, request: FastAPIRequest) -> List[Dict[str, object]]:
        token = self.token_for_request(request)
        if not token:
            raise HTTPException(status_code=401, detail="Connect GitHub before listing repositories")
        payload = self._api(token, "/user/repos?visibility=all&affiliation=owner,collaborator,organization_member&per_page=100")
        if not isinstance(payload, list):
            return []
        return [
            {
                "id": item.get("id"),
                "full_name": item.get("full_name"),
                "private": bool(item.get("private")),
                "clone_url": item.get("clone_url"),
                "default_branch": item.get("default_branch"),
            }
            for item in payload
            if isinstance(item, dict) and isinstance(item.get("full_name"), str)
        ]

    def repository_refs(self, request: FastAPIRequest, owner: str, name: str) -> Dict[str, object]:
        token = self.token_for_request(request)
        if not token:
            raise HTTPException(status_code=401, detail="Connect GitHub before listing repository revisions")
        if not owner or not name or any(part in {".", ".."} for part in (owner, name)):
            raise HTTPException(status_code=422, detail="Invalid GitHub repository name")
        payload = self._api(token, "/repos/{}/{}/git/refs?per_page=100".format(owner, name.removesuffix(".git")))
        refs = []
        if isinstance(payload, list):
            for item in payload:
                ref = item.get("ref") if isinstance(item, dict) else None
                sha = ((item.get("object") or {}).get("sha") if isinstance(item, dict) and isinstance(item.get("object"), dict) else None)
                if isinstance(ref, str) and isinstance(sha, str):
                    refs.append({"ref": ref.removeprefix("refs/heads/"), "sha": sha})
        return {"owner": owner, "name": name.removesuffix(".git"), "refs": refs}

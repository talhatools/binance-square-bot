"""Binance Square OpenAPI Publisher: Handles presigned URL, S3 upload, polling, and post publication."""
import os
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger(__name__)

BASE_URL_V1 = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi"
BASE_URL_V2 = "https://www.binance.com/bapi/composite/v2/public/pgc/openApi"
POLL_INTERVAL_SEC = 3
MAX_POLL_RETRIES = 10


class SquareAPIError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"Binance Square API error [{code}]: {message}")
        self.code = code
        self.message = message


class SquarePublisher:
    def __init__(
        self,
        api_key: Optional[str] = None,
        dry_run: bool = True,
        max_retries: int = 3,
        retry_delay_base: float = 2.0,
    ):
        self.api_key = api_key or os.getenv("BINANCE_SQUARE_OPENAPI_KEY", "").strip()
        self.dry_run = dry_run
        self.max_retries = max_retries
        self.retry_delay_base = retry_delay_base
        self.session = requests.Session()

    def _headers(self) -> Dict[str, str]:
        return {
            "X-Square-OpenAPI-Key": self.api_key,
            "Content-Type": "application/json",
            "clienttype": "binanceSkill",
        }

    def _api_call(
        self, endpoint: str, body: Dict[str, Any], base_url: str = BASE_URL_V2
    ) -> Dict[str, Any]:
        """Makes an authenticated POST request to the Binance Square OpenAPI."""
        if not self.api_key:
            raise SquareAPIError("220003", "Missing Binance Square OpenAPI Key.")

        url = f"{base_url}{endpoint}"
        last_error = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Calling Square API: {url} (Attempt {attempt + 1})")
                res = self.session.post(
                    url,
                    headers=self._headers(),
                    json=body,
                    timeout=15,
                )

                # Special case: 504 gateway timeout on content/add
                if endpoint == "/content/add" and res.status_code == 504:
                    logger.warning("Gateway timeout 504 on /content/add - treating as submitted.")
                    return {
                        "id": None,
                        "shareLink": None,
                        "publishStatus": "success_without_post_id",
                    }

                try:
                    json_data = res.json()
                except Exception:
                    raise RuntimeError(f"Non-JSON response from {endpoint}: {res.status_code} {res.text}")

                code = str(json_data.get("code", ""))
                msg = str(json_data.get("message", ""))

                if code != "000000":
                    # Specific error code identification
                    if code == "220003":
                        logger.critical("Square API Error 220003: API key not found.")
                    elif code == "220004":
                        logger.critical("Square API Error 220004: API key expired.")
                    elif code == "220009":
                        logger.warning("Square API Error 220009: Daily post limit (100) reached.")

                    raise SquareAPIError(code, msg)

                return json_data.get("data", {})

            except SquareAPIError:
                # Do not retry on explicit business logic errors (e.g. key expired or daily limit)
                raise
            except requests.RequestException as exc:
                last_error = exc
                delay = self.retry_delay_base * (2 ** attempt)
                logger.warning(f"Square API connection error: {exc}. Retrying in {delay:.1f}s...")
                time.sleep(delay)

        raise RuntimeError(f"Square API request to {endpoint} failed after retries: {last_error}")

    def upload_image(self, image_path: Path | str) -> str:
        """
        Uploads an image file to Binance Square:
        1. Requests presigned S3 URL and fileTicket.
        2. Uploads binary bytes directly to S3 via PUT.
        3. Polls /image/imageStatus until ready.
        """
        path_obj = Path(image_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Image file does not exist: {image_path}")

        if self.dry_run:
            logger.info(f"[DRY_RUN] Simulating image upload for {path_obj.name}")
            return f"https://binance.com/fake_uploaded_image_{path_obj.name}"

        image_name = path_obj.name
        content_type = "image/png" if image_name.endswith(".png") else "image/jpeg"

        logger.info(f"Requesting presigned upload URL for: {image_name}")
        presigned_data = self._api_call("/image/presignedUrl", {"imageName": image_name})
        presigned_url = presigned_data.get("presignedUrl")
        file_ticket = presigned_data.get("fileTicket")

        if not presigned_url or not file_ticket:
            raise RuntimeError(f"Invalid presigned URL response: {presigned_data}")

        # Upload image to S3
        with open(path_obj, "rb") as f:
            image_bytes = f.read()

        logger.info("Uploading image payload to S3...")
        s3_res = requests.put(
            presigned_url,
            headers={"Content-Type": content_type},
            data=image_bytes,
            timeout=30,
        )
        if not s3_res.ok:
            raise RuntimeError(f"S3 upload failed: {s3_res.status_code} {s3_res.text}")

        # Poll image processing status
        logger.info(f"Polling image processing status for ticket: {file_ticket}...")
        for i in range(MAX_POLL_RETRIES):
            time.sleep(POLL_INTERVAL_SEC)
            status_data = self._api_call("/image/imageStatus", {"fileTicket": file_ticket})
            status = status_data.get("status")

            if status == 1:
                image_url = status_data.get("imageUrl")
                logger.info(f"Image ready for Binance Square: {image_url}")
                return image_url
            elif status == 2:
                reason = status_data.get("failedReason", "Unknown failure")
                raise RuntimeError(f"Binance Square image processing failed: {reason}")
            else:
                logger.debug(f"Image processing in progress ({i + 1}/{MAX_POLL_RETRIES})...")

        raise TimeoutError("Binance Square image upload status poll timed out.")

    def publish_post(
        self,
        text: str,
        image_paths: Optional[List[Path | str]] = None,
    ) -> Dict[str, Any]:
        """
        Publishes a short post (contentType=1) with 1 to 4 images to Binance Square.
        """
        image_paths = image_paths or []
        if len(image_paths) > 4:
            raise ValueError(f"Binance Square supports a maximum of 4 images per post. Given: {len(image_paths)}")

        if self.dry_run:
            logger.info(
                f"[DRY_RUN] Successfully simulated Binance Square post:\n"
                f"--- POST PREVIEW ({len(text)} chars) ---\n{text}\n"
                f"--- ATTACHED IMAGES: {[str(p) for p in image_paths]} ---\n"
            )
            sim_id = f"dry_run_{int(time.time())}"
            return {
                "id": sim_id,
                "shareLink": "https://www.binance.com/en/square/preview-dry-run",
                "publishStatus": "dry_run",
            }

        # 1. Upload images
        uploaded_urls = []
        for img_path in image_paths:
            url = self.upload_image(img_path)
            uploaded_urls.append(url)

        # 2. Build payload
        payload = {
            "contentType": 1,
            "bodyTextOnly": text,
        }
        if uploaded_urls:
            payload["imageList"] = uploaded_urls

        logger.info(f"Publishing post to Binance Square with {len(uploaded_urls)} image(s)...")
        result = self._api_call("/content/add", payload, base_url=BASE_URL_V1)
        logger.info(
            f"Successfully published to Binance Square! "
            f"Post ID: {result.get('id')} | Link: {result.get('shareLink')}"
        )
        return result

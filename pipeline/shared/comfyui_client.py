#!/usr/bin/env python3
"""comfyui_client.py — ComfyUI API 클라이언트.

Flux 1 Dev + Flat_Anime LoRA 워크플로를 ComfyUI API로 실행.
diffusers 사용 안 함 — 모든 생성은 ComfyUI 서버 경유.

Usage:
    from comfyui_client import ComfyUIClient

    client = ComfyUIClient()
    client.health_check()  # 서버 + GPU 확인

    prompt_id = client.queue_workflow(workflow_json, overrides={
        "KSampler": {"seed": 42},
        "EmptyLatentImage": {"width": 1024, "height": 1344},
    })
    result = client.wait_for_completion(prompt_id, timeout=120)
    image_bytes = client.get_image(result["images"][0])
"""

import json
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gpu_utils import check_gpu, check_comfyui as _check_comfyui_gpu

COMFYUI_DEFAULT_URL = "http://127.0.0.1:8188"


class ComfyUIClient:
    """ComfyUI HTTP API 클라이언트.

    ComfyUI 서버가 로컬에서 실행 중이어야 함.
    Flux 1 Dev GGUF 모델을 사용하며, Dynamic VRAM으로 자동 모델 언로드 처리.
    """

    def __init__(self, url: str = COMFYUI_DEFAULT_URL, client_id: str = None):
        self.url = url.rstrip("/")
        self.client_id = client_id or str(uuid.uuid4())

    def health_check(self, min_free_gb: float = 4.0) -> dict:
        """ComfyUI 서버 + GPU 상태 동시 체크.

        Returns: {"gpu": {...}, "comfyui_ok": bool, "comfyui_queue": int}
        Raises SystemExit if server unreachable or VRAM insufficient.
        """
        return _check_comfyui_gpu(
            comfyui_url=self.url,
            min_free_gb=min_free_gb,
            verbose=True,
        )

    def queue_workflow(self, workflow: dict, overrides: dict = None) -> str:
        """워크플로를 ComfyUI 큐에 제출.

        Args:
            workflow: ComfyUI API format workflow JSON (node_id → node_config)
            overrides: {node_title_or_id: {param: value}} — 노드 파라미터 오버라이드

        Returns: prompt_id (str)
        """
        # Apply overrides
        if overrides:
            workflow = self._apply_overrides(workflow, overrides)

        payload = {
            "prompt": workflow,
            "client_id": self.client_id,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.url}/prompt",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                prompt_id = result.get("prompt_id")
                if not prompt_id:
                    raise RuntimeError(f"ComfyUI returned no prompt_id: {result}")
                return prompt_id
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            raise RuntimeError(f"ComfyUI queue failed ({e.code}): {body}") from e

    def wait_for_completion(self, prompt_id: str, timeout: int = 300,
                            poll_interval: float = 3.0) -> dict:
        """prompt_id 실행 완료 대기.

        Returns: {"images": [...], "videos": [...], "outputs": {...}}
        Raises RuntimeError on execution error, TimeoutError on timeout.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            history = self._get_history(prompt_id)
            if history:
                # Check for error status
                status = history.get("status", {})
                status_str = status.get("status_str", "")

                if status_str == "error":
                    # Extract error message from messages
                    err_msg = "Unknown error"
                    for msg in status.get("messages", []):
                        if msg[0] == "execution_error":
                            err_msg = msg[1].get("exception_message", err_msg)
                            break
                    raise RuntimeError(f"ComfyUI execution error: {err_msg}")

                if status_str == "success":
                    outputs = history.get("outputs", {})
                    images = []
                    videos = []
                    for node_id, node_out in outputs.items():
                        for img in node_out.get("images", []):
                            images.append(img)
                        for video in node_out.get("gifs", []):
                            videos.append(video)
                        for video in node_out.get("videos", []):
                            videos.append(video)
                    return {"images": images, "videos": videos, "outputs": outputs}

            time.sleep(poll_interval)

        raise TimeoutError(f"ComfyUI prompt {prompt_id} didn't complete within {timeout}s")

    def get_image(self, image_info: dict) -> bytes:
        """생성된 이미지 바이너리 가져오기.

        Args:
            image_info: {"filename": str, "subfolder": str, "type": str}

        Returns: PNG image bytes
        """
        params = urllib.parse.urlencode({
            "filename": image_info["filename"],
            "subfolder": image_info.get("subfolder", ""),
            "type": image_info.get("type", "output"),
        })
        req = urllib.request.Request(f"{self.url}/view?{params}", method="GET")

        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()

    def upload_image(self, image_path: str, subfolder: str = "",
                     image_type: str = "input") -> dict:
        """이미지를 ComfyUI input 디렉토리에 업로드.

        Args:
            image_path: 로컬 이미지 파일 경로
            subfolder: ComfyUI 내 서브폴더
            image_type: "input" or "temp"

        Returns: {"name": str, "subfolder": str, "type": str}
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # multipart/form-data 수동 구성
        boundary = f"----ComfyUIBoundary{uuid.uuid4().hex[:12]}"
        body = b""

        # image field
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="image"; filename="{path.name}"\r\n'.encode()
        body += b"Content-Type: image/png\r\n\r\n"
        body += path.read_bytes()
        body += b"\r\n"

        # subfolder field
        if subfolder:
            body += f"--{boundary}\r\n".encode()
            body += b'Content-Disposition: form-data; name="subfolder"\r\n\r\n'
            body += subfolder.encode()
            body += b"\r\n"

        # type field
        body += f"--{boundary}\r\n".encode()
        body += b'Content-Disposition: form-data; name="type"\r\n\r\n'
        body += image_type.encode()
        body += b"\r\n"

        body += f"--{boundary}--\r\n".encode()

        req = urllib.request.Request(
            f"{self.url}/upload/image",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def interrupt(self):
        """현재 실행 중인 generation 중단."""
        req = urllib.request.Request(
            f"{self.url}/interrupt",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read()

    # --- Internal helpers ---

    def _get_history(self, prompt_id: str) -> dict | None:
        """prompt 실행 히스토리 조회. 완료 안 됐으면 None."""
        try:
            req = urllib.request.Request(
                f"{self.url}/history/{prompt_id}", method="GET"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                return data.get(prompt_id)
        except (urllib.error.URLError, json.JSONDecodeError):
            return None

    def _get_queue(self) -> dict:
        """현재 큐 상태 조회."""
        try:
            req = urllib.request.Request(f"{self.url}/queue", method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, json.JSONDecodeError):
            return {}

    def _apply_overrides(self, workflow: dict, overrides: dict) -> dict:
        """노드 파라미터 오버라이드 적용.

        overrides key: node_id (str) or node _meta.title (str)
        """
        import copy
        wf = copy.deepcopy(workflow)

        # Build title→id lookup
        title_to_id = {}
        for node_id, node in wf.items():
            title = node.get("_meta", {}).get("title", "")
            if title:
                title_to_id[title] = node_id

        for key, params in overrides.items():
            # Resolve key to node_id
            node_id = key if key in wf else title_to_id.get(key)
            if node_id is None:
                print(f"  [ComfyUI] WARNING: Override target '{key}' not found in workflow")
                continue

            node = wf[node_id]
            inputs = node.get("inputs", {})
            for param_name, param_value in params.items():
                if param_name in inputs:
                    inputs[param_name] = param_value
                else:
                    # Try nested
                    inputs[param_name] = param_value
            node["inputs"] = inputs

        return wf


def load_workflow(workflow_path: str) -> dict:
    """워크플로 JSON 파일 로드.

    Args:
        workflow_path: 절대경로 or 프로젝트 루트 상대경로
    """
    p = Path(workflow_path)
    if not p.is_absolute():
        project_root = Path(__file__).resolve().parent.parent.parent
        p = project_root / p

    if not p.exists():
        raise FileNotFoundError(f"Workflow not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    print("=" * 60)
    print("ComfyUI Client — Health Check")
    print("=" * 60)
    client = ComfyUIClient()
    try:
        result = client.health_check(min_free_gb=2.0)
        print(f"\nAll checks passed. Queue: {result['comfyui_queue']}")
    except SystemExit:
        print("\nHealth check failed. See above for details.")

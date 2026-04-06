"""Minimal interceptor - only parses API responses for metadata enrichment."""
import time

API_PATTERNS = ("/api/", "/tiktok/", "/node/")


class VideoInterceptor:
    def __init__(self):
        self.video_metadata: dict[str, dict] = {}

    async def on_response(self, response):
        url = response.url
        if any(p in url for p in API_PATTERNS):
            await self._parse_api(response)

    def get_metadata(self, video_id: str) -> dict:
        return self.video_metadata.get(video_id, {})

    async def _parse_api(self, response):
        try:
            ct = response.headers.get("content-type", "")
            if "json" not in ct:
                return
            data = await response.json()
        except Exception:
            return
        try:
            items = []
            if isinstance(data, dict):
                for key in ("itemList", "items"):
                    if key in data:
                        items = data[key] or []
                        break
                if not items and "itemInfo" in data:
                    items = [data["itemInfo"].get("itemStruct", {})]
                if not items and "data" in data and isinstance(data["data"], dict):
                    d = data["data"]
                    items = d.get("items") or d.get("itemList") or []

            for item in items:
                if not isinstance(item, dict):
                    continue
                vid = str(item.get("id", ""))
                if not vid:
                    continue
                author_info = item.get("author", {})
                author = ""
                if isinstance(author_info, dict):
                    author = author_info.get("uniqueId") or author_info.get("nickname", "")

                # Extract image URLs for photo posts
                image_urls = []
                image_post = item.get("imagePost", {})
                if isinstance(image_post, dict):
                    for img in image_post.get("images", []):
                        if not isinstance(img, dict):
                            continue
                        url_list = img.get("imageURL", {}).get("urlList", [])
                        if url_list:
                            image_urls.append(url_list[0])

                self.video_metadata[vid] = {
                    "author": author,
                    "desc": item.get("desc", ""),
                    "type": "photo" if image_urls else "video",
                    "image_urls": image_urls,
                }
        except Exception:
            pass

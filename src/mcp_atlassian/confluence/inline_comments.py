"""
Mixin for Confluence inline-comment operations (Cloud only, REST v2).
"""

from __future__ import annotations
import logging
import requests

from .client import ConfluenceClient
from ..models.confluence import ConfluenceComment

logger = logging.getLogger("mcp-atlassian")


class InlineCommentsMixin(ConfluenceClient):
    """
    Cloud-only helper for fetching *inline* comments on a page.
    """

    _V2_ENDPOINT_TMPL = "/wiki/api/v2/pages/{page_id}/inline-comments"

    def get_inline_comments(
        self,
        page_id: str,
        *,                      # keyword-only
        return_markdown: bool = True,
    ) -> list[ConfluenceComment]:
        """
        Retrieve **all** inline comments for a given Confluence page.

        Args
        ----
        page_id : str
            The numeric content-id of the page.
        return_markdown : bool, default True
            If True → body is converted to Markdown;
            else → original HTML (storage) is returned.

        Returns
        -------
        list[ConfluenceComment] – simplified, markdown-ready models.
        """
        results: list[ConfluenceComment] = []

        try:
            # Need space_key for URL-fix-ups in the pre-processor.
            page = self.confluence.get_page_by_id(page_id=page_id, expand="space")
            space_key = page.get("space", {}).get("key", "")

            url = f"{self.config.url}{self._V2_ENDPOINT_TMPL.format(page_id=page_id)}"
            params: dict[str, str | int] = {"limit": 100}
            session = self.confluence._session  # authenticated Session

            while True:
                r = session.get(url, params=params, timeout=30)
                r.raise_for_status()
                payload = r.json()
                for c in payload.get("results", []):
                    body_html = c["body"]["storage"]["value"]
                    processed_html, processed_md = self.preprocessor.process_html_content(
                        body_html, space_key=space_key
                    )

                    # Mutate copy so ConfluenceComment factory sees the right field.
                    c_mod = c.copy()
                    c_mod.setdefault("body", {}).setdefault("storage", {})[
                        "value"
                    ] = processed_md if return_markdown else processed_html

                    results.append(
                        ConfluenceComment.from_api_response(
                            c_mod,
                            base_url=self.config.url,
                        )
                    )

                if "next" not in payload.get("_links", {}):
                    break               # no more pages
                url = payload["_links"]["next"]

        except (requests.RequestException, KeyError) as exc:
            logger.error("Error fetching inline comments: %s", exc)
        return results
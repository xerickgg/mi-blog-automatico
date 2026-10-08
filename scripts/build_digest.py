#!/usr/bin/env python3
"""Build a static, attributed RSS digest for GitHub Pages."""

from __future__ import annotations

import datetime as dt
import html
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


FEEDS = [
    ("NASA", "https://www.nasa.gov/news-release/feed/"),
    ("Python Insider", "https://feeds.feedburner.com/PythonInsider"),
    ("GitHub Changelog", "https://github.blog/changelog/feed/"),
]
OUTPUT = Path("site/index.html")
MAX_PER_FEED = 12
USER_AGENT = "DailyPublicDigest/1.0 (+https://github.com)"


def clean_text(value: str | None) -> str:
    """Remove markup and normalize whitespace from an RSS field."""
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(value).split())


def parse_date(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.astimezone(dt.timezone.utc)
        except ValueError:
            return None


def fetch_feed(name: str, feed_url: str) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        feed_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"{name}: RSS returned HTTP {response.status}")
        root = ET.fromstring(response.read())

    entries = []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1].lower()
        if tag not in {"item", "entry"}:
            continue

        fields: dict[str, str] = {}
        link = ""
        for child in node:
            child_tag = child.tag.rsplit("}", 1)[-1].lower()
            if child_tag == "link":
                link = child.attrib.get("href", child.text or "").strip()
            elif child_tag in {"title", "published", "updated", "pubdate", "description", "summary"}:
                fields.setdefault(child_tag, "".join(child.itertext()).strip())

        title = clean_text(fields.get("title"))
        if not link or not title:
            continue

        parsed_link = urlparse(link)
        if parsed_link.scheme not in {"http", "https"}:
            continue

        published = parse_date(
            fields.get("published")
            or fields.get("updated")
            or fields.get("pubdate")
        )

        entries.append({
            "source": name,
            "title": title,
            "url": link,
            "published": published,
        })

    entries.sort(
        key=lambda item: item["published"] or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
        reverse=True,
    )
    return entries[:MAX_PER_FEED]


def render(items: list[dict[str, Any]]) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    cards = []

    for item in items:
        date_text = (
            item["published"].strftime("%Y-%m-%d %H:%M UTC")
            if item["published"]
            else "Fecha no indicada"
        )
        cards.append(
            "<article class=\"item\">"
            f"<p class=\"meta\">{html.escape(item['source'])} · {html.escape(date_text)}</p>"
            f"<h2><a href=\"{html.escape(item['url'], quote=True)}\" "
            "rel=\"noopener noreferrer\">"
            f"{html.escape(item['title'])}</a></h2>"
            "</article>"
        )

    body = "\n".join(cards) if cards else "<p>No se encontraron entradas en esta ejecución.</p>"

    # Configure these as GitHub repository variables after the ad provider
    # approves the site. Leave empty to publish without an ad slot.
    ad_client = os.getenv("ADSENSE_CLIENT", "").strip()
    ad_slot = os.getenv("ADSENSE_SLOT", "").strip()
    ad_markup = ""
    if ad_client and ad_slot:
        ad_markup = (
            "<section class=\"ad\" aria-label=\"Publicidad\">"
            "<ins class=\"adsbygoogle\" style=\"display:block\" "
            f"data-ad-client=\"{html.escape(ad_client, quote=True)}\" "
            f"data-ad-slot=\"{html.escape(ad_slot, quote=True)}\" "
            "data-ad-format=\"auto\" data-full-width-responsive=\"true\"></ins>"
            "<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>"
            "</section>"
        )
        ad_script = (
            "<script async "
            f"src=\"https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js"
            f"?client={html.escape(ad_client, quote=True)}\" "
            "crossorigin=\"anonymous\"></script>"
        )
    else:
        ad_script = ""

    return f"""<!doctype html>
<html lang="es">
<head>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2551421392442499"
     crossorigin="anonymous"></script>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Resumen diario de fuentes públicas</title>
  <meta name="description" content="Selección diaria de publicaciones públicas con enlaces a sus fuentes originales.">
  {ad_script}
  <style>
    body {{ max-width: 850px; margin: 2rem auto; padding: 0 1rem;
           font: 1rem/1.6 system-ui, sans-serif; color: #202124; }}
    h1 {{ line-height: 1.2; }}
    .item {{ border-top: 1px solid #ddd; padding: 1rem 0; }}
    .item h2 {{ margin: .2rem 0; font-size: 1.2rem; }}
    .meta, footer {{ color: #5f6368; font-size: .9rem; }}
    a {{ color: #1358a8; }}
    .ad {{ margin: 2rem 0; min-height: 90px; }}
  </style>
</head>
<body>
  <header>
    <h1>Resumen diario</h1>
    <p>Publicaciones recientes, enlazadas a sus fuentes originales.</p>
    <p class="meta">Actualizado: {now.strftime("%Y-%m-%d %H:%M UTC")}</p>
  </header>
  {ad_markup}
  <main>{body}</main>
  <footer><p>Los enlaces conducen a las fuentes originales. Se muestran títulos y atribución.</p></footer>
</body>
</html>
"""


def main() -> None:
    items = []
    failures = []

    for name, url in FEEDS:
        try:
            items.extend(fetch_feed(name, url))
        except (OSError, ET.ParseError, RuntimeError, urllib.error.URLError) as exc:
            failures.append(f"{name}: {exc}")

    if not items:
        raise RuntimeError("No se obtuvieron entradas de ninguna fuente. " + "; ".join(failures))

    items.sort(
        key=lambda item: item["published"] or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
        reverse=True,
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(items), encoding="utf-8")
    print(f"Published {len(items)} entries to {OUTPUT}")

    if failures:
        print("Feed errors: " + " | ".join(failures))


if __name__ == "__main__":
    main()

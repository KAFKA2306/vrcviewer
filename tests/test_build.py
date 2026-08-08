from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vrcviewer.build import BuildError, load_catalog, render_page, run

HEADER = "ID,Name,Author ID,Author Name,Thumbnail\n"
AVATAR_ID = "avtr_11111111-1111-1111-1111-111111111111"
WORLD_ID = "wrld_22222222-2222-2222-2222-222222222222"
AUTHOR_ID = "usr_33333333-3333-3333-3333-333333333333"
THUMB = "https://example.invalid/image.png"
TEMPLATE = "A{{AVATAR_CARDS}}B{{WORLD_FILTERS}}C{{WORLD_CARDS}}D\n"


class BuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "templates").mkdir()
        (self.root / "templates" / "index.html").write_text(TEMPLATE, encoding="utf-8")
        self.write_avatar("Sample avatar")
        self.write_world(self.root / "worlds_chill.csv", WORLD_ID, "Sample world")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_avatar(self, name: str, thumbnail: str = THUMB) -> None:
        (self.root / "sample_avatars.csv").write_text(
            HEADER + f'{AVATAR_ID},"{name}",{AUTHOR_ID},Creator,{thumbnail}\n',
            encoding="utf-8",
        )

    def write_world(self, path: Path, world_id: str, name: str, thumbnail: str = THUMB) -> None:
        path.write_text(
            HEADER + f'{world_id},"{name}",{AUTHOR_ID},Creator,{thumbnail}\n',
            encoding="utf-8",
        )

    def test_same_inputs_render_byte_identically_and_sort_categories(self) -> None:
        self.write_world(
            self.root / "worlds_event.csv",
            "wrld_44444444-4444-4444-4444-444444444444",
            "Event",
        )
        first, counts, paths = render_page(self.root)
        second, _, _ = render_page(self.root)
        self.assertEqual(first.encode(), second.encode())
        self.assertLess(first.index('data-filter="chill"'), first.index('data-filter="event"'))
        self.assertEqual(counts["worlds"], 2)
        self.assertEqual([path.name for path in paths], ["sample_avatars.csv", "worlds_chill.csv", "worlds_event.csv"])

    def test_html_and_attribute_values_are_escaped(self) -> None:
        self.write_avatar('<img src=x onerror="alert(1)"> & test')
        page, _, _ = render_page(self.root)
        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; test", page)
        self.assertNotIn('<img src=x onerror="alert(1)">', page)
        self.assertNotIn("onclick=", page)

    def test_csv_supports_comma_quote_newline_unicode_and_emoji(self) -> None:
        name = '日本語, "quoted"\n🌏 world'
        self.write_world(self.root / "worlds_chill.csv", WORLD_ID, name)
        worlds = load_catalog(self.root)[1]
        self.assertEqual(len(worlds), 1)
        self.assertIn("日本語", worlds[0].name)

    def test_missing_column_is_rejected_with_file_context(self) -> None:
        (self.root / "sample_avatars.csv").write_text("ID,Name\nfoo,bar\n", encoding="utf-8")
        with self.assertRaisesRegex(BuildError, "sample_avatars.csv.*expected columns"):
            load_catalog(self.root)

    def test_duplicate_world_id_across_categories_is_rejected(self) -> None:
        self.write_world(self.root / "worlds_event.csv", WORLD_ID, "Duplicate")
        with self.assertRaisesRegex(BuildError, "already exists"):
            load_catalog(self.root)

    def test_javascript_thumbnail_and_missing_thumbnail_are_rejected(self) -> None:
        self.write_avatar("unsafe", "javascript:alert(1)")
        with self.assertRaisesRegex(BuildError, "absolute https URL"):
            load_catalog(self.root)
        self.write_avatar("missing", "")
        with self.assertRaisesRegex(BuildError, "Thumbnail must not be empty"):
            load_catalog(self.root)

    def test_invalid_resource_id_reports_row(self) -> None:
        (self.root / "sample_avatars.csv").write_text(
            HEADER + f"not-an-avatar,Name,{AUTHOR_ID},Creator,{THUMB}\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(BuildError, r"sample_avatars.csv:2: invalid avatar ID"):
            load_catalog(self.root)

    def test_failed_build_does_not_replace_existing_index(self) -> None:
        original = b"known-good\n"
        (self.root / "index.html").write_bytes(original)
        (self.root / "sample_avatars.csv").write_text("bad,data\n", encoding="utf-8")
        with self.assertRaises(BuildError):
            run(self.root, check=False)
        self.assertEqual((self.root / "index.html").read_bytes(), original)

    def test_check_detects_stale_generated_html(self) -> None:
        (self.root / "index.html").write_text("stale\n", encoding="utf-8")
        with self.assertRaisesRegex(BuildError, "index.html is stale"):
            run(self.root, check=True)


if __name__ == "__main__":
    unittest.main()

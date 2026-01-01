"""
Post-processor for markdown files to handle multilanguage titles.

Converts files like 'Presense _ Присутствие.md' to:
- Filename: 'Presense.md'
- Frontmatter: aliases: ["Присутствие"]
- Updates all wiki-links across the vault
"""

import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import frontmatter

logger = logging.getLogger(__name__)

# Regex patterns for detecting Cyrillic and Latin characters
CYRILLIC_PATTERN = re.compile(r"[а-яА-ЯёЁ]")
LATIN_PATTERN = re.compile(r"[a-zA-Z]")
PARENTHESES_PATTERN = re.compile(r"^(.+?)\s*\(([^()]+)\)$")
UNDERSCORE_IN_PARENS_PATTERN = re.compile(r"\([^)]*_\s*[^)]*\)")


@dataclass
class TitleParts:
    """Result of parsing a multilanguage title."""

    main_title: str
    aliases: list[str]
    original: str


def is_cyrillic(text: str) -> bool:
    """Check if text contains Cyrillic characters."""
    return bool(CYRILLIC_PATTERN.search(text))


def is_latin(text: str) -> bool:
    """Check if text contains Latin characters."""
    return bool(LATIN_PATTERN.search(text))


def _parse_parentheses_pattern(name: str) -> TitleParts | None:
    """Parse pattern like 'Контекст (Context)' or 'Practice first (сначала попробуй)'."""
    match = PARENTHESES_PATTERN.match(name)
    if not match:
        return None

    main_part = match.group(1).strip()
    alias_part = match.group(2).strip()

    # Skip if alias contains ' _ ' (will be handled by underscore pattern)
    if " _ " in alias_part:
        return None

    main_has_cyrillic = is_cyrillic(main_part)
    main_has_latin = is_latin(main_part)
    alias_has_cyrillic = is_cyrillic(alias_part)
    alias_has_latin = is_latin(alias_part)

    # Russian main, English alias -> use English as main
    if main_has_cyrillic and not main_has_latin and alias_has_latin and not alias_has_cyrillic:
        return TitleParts(main_title=alias_part, aliases=[main_part], original=name)

    # English main, Russian alias -> keep English as main
    if main_has_latin and not main_has_cyrillic and alias_has_cyrillic:
        return TitleParts(main_title=main_part, aliases=[alias_part], original=name)

    # Same language or mixed -> main as title, alias as alias
    return TitleParts(main_title=main_part, aliases=[alias_part], original=name)


def _classify_parts(parts: list[str]) -> tuple[list[str], list[str]]:
    """Classify parts into English and Russian lists."""
    english_parts: list[str] = []
    russian_parts: list[str] = []

    for part in parts:
        has_cyrillic = is_cyrillic(part)
        has_latin = is_latin(part)

        if has_latin and not has_cyrillic:
            english_parts.append(part)
        elif has_cyrillic:
            russian_parts.append(part)

    return english_parts, russian_parts


def _parse_underscore_pattern(name: str) -> TitleParts | None:
    """Parse pattern like 'Presense _ Присутствие' or 'worldview _ horizon _ vision'."""
    # Skip if name has parentheses with '_' inside (technical names)
    if UNDERSCORE_IN_PARENS_PATTERN.search(name):
        return None

    parts = [p.strip() for p in name.split(" _ ")]
    if len(parts) < 2:
        return None

    english_parts, russian_parts = _classify_parts(parts)

    # Multilanguage: has both English and Russian parts
    if english_parts and russian_parts:
        return TitleParts(main_title=english_parts[0], aliases=russian_parts, original=name)

    # All English parts
    if english_parts and len(english_parts) == len(parts):
        return TitleParts(main_title=english_parts[0], aliases=english_parts[1:], original=name)

    # All Russian parts
    if russian_parts and len(russian_parts) == len(parts):
        return TitleParts(main_title=russian_parts[0], aliases=russian_parts[1:], original=name)

    return None


def parse_multilanguage_filename(filename: str) -> TitleParts | None:
    """
    Parse a filename with multiple parts (multilanguage or single-language).

    Examples:
        'Presense _ Присутствие.md' -> main='Presense', aliases=['Присутствие']
        'Контекст (Context).md' -> main='Context', aliases=['Контекст']
        'worldview _ horizon _ vision.md' -> main='worldview', aliases=['horizon', 'vision']
    """
    name = filename.removesuffix(".md")

    # Try parentheses pattern first: "title (alias)"
    result = _parse_parentheses_pattern(name)
    if result:
        return result

    # Try underscore pattern: "title _ alias _ alias2"
    return _parse_underscore_pattern(name)


def update_links_in_content(content: str, old_name: str, new_name: str) -> str:
    """Update wiki-links: [[old_name]] → [[new_name]], [[old_name|display]] → [[new_name|display]]."""
    escaped_old = re.escape(old_name)
    pattern = rf"\[\[{escaped_old}(\|[^\]]+)?\]\]"

    def replace_link(match):
        display_part = match.group(1) or ""
        return f"[[{new_name}{display_part}]]"

    return re.sub(pattern, replace_link, content)


def _copy_to_output_dir(md_path: Path, output_dir: str) -> Path:
    """Copy markdown directory to output directory, return new path."""
    output_path = Path(output_dir)
    logger.info(f"Copying files from {md_path} to {output_dir}")

    if output_path.exists():
        shutil.rmtree(output_path)

    shutil.copytree(md_path, output_path)
    logger.info(f"Copied files to {output_dir}")
    return output_path


def _find_files_to_process(md_path: Path) -> dict[str, TitleParts]:
    """Find all files that need processing and build rename map."""
    rename_map: dict[str, TitleParts] = {}

    for md_file in md_path.rglob("*.md"):
        parts = parse_multilanguage_filename(md_file.name)
        if parts:
            rename_map[str(md_file)] = parts
            logger.info(f"Found: {md_file.name} -> {parts.main_title}.md (aliases: {parts.aliases})")

    logger.info(f"Found {len(rename_map)} files to process")
    return rename_map


def _build_link_replacements(rename_map: dict[str, TitleParts]) -> dict[str, str]:
    """Build mapping of old link names to new link names."""
    return {parts.original: parts.main_title for parts in rename_map.values()}


def _update_links_in_all_files(md_path: Path, link_replacements: dict[str, str]) -> int:
    """Update wiki-links in all markdown files. Returns count of updated files."""
    links_updated = 0

    for md_file in md_path.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            new_content = content

            for old_name, new_name in link_replacements.items():
                new_content = update_links_in_content(new_content, old_name, new_name)

            if new_content != content:
                md_file.write_text(new_content, encoding="utf-8")
                links_updated += 1
                logger.debug(f"Updated links in {md_file}")
        except Exception as e:
            logger.error(f"Failed to update links in {md_file}: {e}")

    logger.info(f"Updated links in {links_updated} files")
    return links_updated


def _add_aliases_to_frontmatter(post: frontmatter.Post, aliases: list[str]) -> None:
    """Add aliases to frontmatter, preserving existing ones."""
    existing_aliases = post.get("aliases", [])
    if isinstance(existing_aliases, str):
        existing_aliases = [existing_aliases]

    for alias in aliases:
        if alias not in existing_aliases:
            existing_aliases.append(alias)

    post["aliases"] = existing_aliases


def _rename_files_and_add_aliases(rename_map: dict[str, TitleParts]) -> int:
    """Rename files and add aliases to frontmatter. Returns count of renamed files."""
    files_renamed = 0

    for old_path_str, parts in rename_map.items():
        old_path = Path(old_path_str)
        new_path = old_path.parent / f"{parts.main_title}.md"

        try:
            post = frontmatter.load(old_path)
            _add_aliases_to_frontmatter(post, parts.aliases)

            with open(new_path, "w", encoding="utf-8") as f:
                f.write(frontmatter.dumps(post))

            if old_path != new_path:
                old_path.unlink()
                files_renamed += 1
                logger.info(f"Renamed: {old_path.name} -> {new_path.name}")
            else:
                logger.info(f"Updated frontmatter: {old_path.name}")

        except Exception as e:
            logger.error(f"Failed to process {old_path}: {e}")

    return files_renamed


def process_markdown_directory(md_root: str, output_dir: str | None = None, dry_run: bool = False) -> dict:
    """
    Process all markdown files: rename files, add aliases, update links.

    Args:
        md_root: Path to markdown directory
        output_dir: If specified, copy to this directory instead of modifying in place
        dry_run: If True, only report what would be done
    """
    md_path = Path(md_root)

    if not md_path.exists():
        logger.warning(f"Markdown directory does not exist: {md_root}")
        return {"error": "directory_not_found"}

    if output_dir and not dry_run:
        md_path = _copy_to_output_dir(md_path, output_dir)

    rename_map = _find_files_to_process(md_path)

    if dry_run:
        return {"files_to_rename": len(rename_map), "rename_map": {k: v.main_title for k, v in rename_map.items()}}

    if not rename_map:
        return {"files_renamed": 0, "links_updated": 0, "total_multilanguage": 0}

    link_replacements = _build_link_replacements(rename_map)
    links_updated = _update_links_in_all_files(md_path, link_replacements)
    files_renamed = _rename_files_and_add_aliases(rename_map)

    return {"files_renamed": files_renamed, "links_updated": links_updated, "total_multilanguage": len(rename_map)}

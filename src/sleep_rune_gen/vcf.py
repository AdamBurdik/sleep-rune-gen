from __future__ import annotations

import argparse
import base64
import re
import sys
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNES = PROJECT_ROOT / "output"
LINE_LIMIT = 75
PHOTO_PREFIX = "data:image/png;base64,"
TRANSLITERATION = {
    "Æ": "A",
    "Œ": "O",
    "Ø": "O",
    "Ł": "L",
    "Đ": "D",
    "Ð": "D",
    "Þ": "T",
    "ß": "S",
}


def property_name(record: list[str]) -> str | None:
    line = record[0]
    if not line or line[0] in " \t":
        return None
    head = line.split(":", 1)[0]
    name = head.split(";", 1)[0].strip()
    return name.rsplit(".", 1)[-1].upper()


def property_value(record: list[str]) -> str | None:
    line = record[0]
    if not line or line[0] in " \t":
        return None
    _, separator, value = line.partition(":")
    if not separator:
        return None
    return value + "".join(continuation[1:] for continuation in record[1:])


def split_escaped(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    escaped = False
    for character in value:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == ";":
            parts.append("".join(current))
            current = []
        else:
            current.append(character)
    parts.append("".join(current))
    return parts


def first_name(records: list[list[str]]) -> str:
    structured = next(
        (property_value(r) for r in records if property_name(r) == "N"), None
    )
    if structured:
        parts = split_escaped(structured)
        if len(parts) > 1 and parts[1].strip():
            return parts[1].strip()

    display = next(
        (property_value(r) for r in records if property_name(r) == "FN"), None
    )
    if display:
        tokens = re.split(r"[\s,]+", display.strip())
        if tokens and tokens[0]:
            return tokens[0]

    return ""


def initial_of(name: str) -> str | None:
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    for character in normalized.upper():
        if "A" <= character <= "Z":
            return character
        if character in TRANSLITERATION:
            return TRANSLITERATION[character]
        if character.isalpha():
            return None
    return None


def fold_property(prop: str) -> list[str]:
    lines = [prop[:LINE_LIMIT]]
    remainder = prop[LINE_LIMIT:]
    while remainder:
        chunk = remainder[: LINE_LIMIT - 1]
        lines.append(" " + chunk)
        remainder = remainder[len(chunk) :]
    return lines


def split_records(lines: list[str]) -> list[list[str]]:
    records: list[list[str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line[:1] in (" ", "\t"):
            records.append([line])
            index += 1
            continue
        record = [line]
        index += 1
        while index < len(lines) and lines[index][:1] in (" ", "\t"):
            record.append(lines[index])
            index += 1
        records.append(record)
    return records


def process_block(
    block: list[list[str]],
    runes_dir: Path,
    rune_cache: dict[str, bytes],
) -> tuple[list[list[str]], str | None, str | None, str]:
    name = first_name(block)
    initial = initial_of(name)
    if initial is None:
        return block, None, name or None, "skipped"

    if initial not in rune_cache:
        rune_path = runes_dir / f"{initial}.png"
        if not rune_path.is_file():
            return block, initial, name or None, "missing"
        data = rune_path.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            return block, initial, name or None, "invalid"
        rune_cache[initial] = data

    encoded = base64.b64encode(rune_cache[initial]).decode("ascii")
    photo_record = fold_property("PHOTO:" + PHOTO_PREFIX + encoded)

    output: list[list[str]] = []
    replaced = False
    for record in block:
        if property_name(record) == "PHOTO":
            output.append(photo_record)
            replaced = True
        else:
            output.append(record)

    if not replaced:
        end_index = next(
            (i for i, r in enumerate(output) if property_name(r) == "END"), None
        )
        if end_index is None:
            return output, initial, name or None, "skipped"
        insert_index = end_index
        while insert_index > 0 and property_name(output[insert_index - 1]) is None:
            insert_index -= 1
        output.insert(insert_index, photo_record)
        return output, initial, name or None, "added"

    return output, initial, name or None, "replaced"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replace vCard photos with generated Sleep Token rune images."
    )
    parser.add_argument("input", help="Input .vcf file")
    parser.add_argument(
        "--output",
        default=None,
        help="Output .vcf path (default: <input>_runes.vcf)",
    )
    parser.add_argument(
        "--runes",
        default=str(DEFAULT_RUNES),
        help="Directory containing A.png ... Z.png",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        raise SystemExit(f"Input file not found: {input_path}")

    runes_dir = Path(args.runes)
    if not runes_dir.is_dir():
        raise SystemExit(f"Runes directory not found: {runes_dir}")

    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_name(f"{input_path.stem}_runes.vcf")
    )

    with input_path.open(encoding="utf-8", newline="") as handle:
        text = handle.read()
    if "\r\n" in text:
        newline = "\r\n"
    elif "\r\n" not in text and "\r" in text and "\n" not in text:
        newline = "\r"
    else:
        newline = "\n"
    final_newline = text.endswith(("\n", "\r"))

    records = split_records(text.splitlines())
    result: list[list[str]] = []
    rune_cache: dict[str, bytes] = {}
    counts = {"replaced": 0, "added": 0, "skipped": 0, "missing": 0, "invalid": 0}

    index = 0
    while index < len(records):
        if property_name(records[index]) == "BEGIN":
            end_index = index
            while end_index < len(records) and property_name(records[end_index]) != "END":
                end_index += 1
            if end_index >= len(records):
                result.extend(records[index:])
                break
            block = records[index : end_index + 1]
            processed, initial, name, status = process_block(
                block, runes_dir, rune_cache
            )
            result.extend(processed)
            counts[status] += 1
            label = name or "(no name)"
            detail = f" -> {initial}" if initial else ""
            print(f"{status}: {label}{detail}", file=sys.stderr)
            index = end_index + 1
        else:
            result.append(records[index])
            index += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = newline.join(line for record in result for line in record)
    if final_newline:
        content += newline
    output_path.write_text(content, encoding="utf-8", newline="")

    print(
        f"Contacts: {counts['replaced'] + counts['added'] + counts['skipped'] + counts['missing'] + counts['invalid']}, "
        f"replaced: {counts['replaced']}, added: {counts['added']}, "
        f"skipped: {counts['skipped']}, missing runes: {counts['missing']}, "
        f"invalid runes: {counts['invalid']}"
    )
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()

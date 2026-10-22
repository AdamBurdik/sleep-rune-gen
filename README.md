> [!NOTE]
> This project was written entirely by AI. I was lazy to do it myself

# sleep-rune-gen

Makes images with Sleep Token runes on a background, then can use them as contact photos.

## Setup

You need [uv](https://docs.astral.sh/uv/). Then run:

```
uv sync
```

## Generate the images

```
uv run sleep-rune-gen
```

This creates `A.png` to `Z.png` in `output/`. The background is `assets/background.png`.

The script looks for `SleepTokenRunes-Regular.ttf` in `assets/` first, then in `~/.local/share/fonts/`.

## Add runes to contacts

```
uv run sleep-rune-vcf contacts.vcf
```

This writes `contacts_runes.vcf` and leaves the original file alone. For each contact it takes the first letter of the first name and uses that rune as the photo. If the contact has no photo, it adds one.

Names with accents are mapped to a normal letter (`Š` becomes `S`). Other names are skipped and a warning is printed.

Use `--output` to pick another output file and `--runes` to use another image folder.

# 3DCP Sticker Vault

Welcome to the sticker shelf for **3D Changes Perspectives** (**3DCP**). These images are made for viewers who want to react, remix, share, and carry a little of the show into their own conversations. Use **#3DCP** when sharing them or talking about the show.

> **Quick start:** Browse the full sticker folder on GitHub: [3DCP Sticker Folder](https://github.com/DigiMancer3D/3DChangesPerspectives/tree/main/stickers)  
> Open the [web sticker gallery](https://gistpreview.github.io/?ffcd773b7d7414d987077edc4f5916c5/3DCP_StickerGallery.html) for a browser-based preview, with direct download options where provided. You can also open the local [`gallery.html`](./gallery.html) page or download an image directly from this folder. The matching `.bnpm` files are optional reconstruction recipes for people who want to reproduce the image from a local Bitcoin (BTC) blockchain corpus using [Block-n-Pick](https://github.com/DigiMancer3D/Block-n-Pick).

## What's here

- **Ready-to-use images:** PNG and JPG files for sharing and sticker-making.
- **Web gallery:** [Open the 3DCP Sticker Gallery](https://gistpreview.github.io/?ffcd773b7d7414d987077edc4f5916c5/3DCP_StickerGallery.html) to browse the collection online.
- **GitHub folder:** [Browse all sticker files](https://github.com/DigiMancer3D/3DChangesPerspectives/tree/main/stickers)
- **Local gallery view:** `gallery.html` gives a fast visual preview and direct download controls when opened in a browser.
- **BNPM companions:** Files such as `3D Close Up_bnp.bnpm` and `Catch_up_deets_bnp2.bnpm` that can be resolved and built with Block-n-Pick.
- **Show identity:** 3DCP logos, character art, reactions, catch-up cards, and meme-style visual references.

The collection will grow as new episodes and visual bits are released. File names are kept descriptive where possible; the original image formats are preserved so you can choose the quality and workflow that fits your platform.

## Creative note

These stickers are AI-made with my model and draw on online meme imagery and nerd references. They are fan-facing show artwork and visual jokes—not a claim that every underlying reference is original to this project. Please respect the rights, trademarks, likenesses, and platform rules that may apply to third-party material, and do not imply endorsement by any referenced creator or brand.

For the safest sharing workflow, link back to this repository, credit **3D Changes Perspectives**, and use **#3DCP**. If you remix something, make it clear that your version is a remix.

## Browser gallery

- [Open the web version of the 3DCP Sticker Gallery](https://gistpreview.github.io/?ffcd773b7d7414d987077edc4f5916c5/3DCP_StickerGallery.html)
- [Browse the sticker files in GitHub](https://github.com/DigiMancer3D/3DChangesPerspectives/tree/main/stickers)
- [Open the local gallery page](./gallery.html)

The web gallery is the easiest option for viewers who want to preview the sticker pack online without downloading the repository first.

## Reconstructing a `.bnpm` image with Block-n-Pick

A `.bnpm` file is a Block-n-Pick recipe. It describes fragments that can be resolved from an independently verifiable blockchain hash corpus; it does **not** mean that the finished image is literally stored in Bitcoin. Reconstruction is a local computation performed from the recipe and the sources available to you.

### Requirements

1. A local copy of the BTC blockchain or a reachable local Bitcoin node that Block-n-Pick can use for acquisition.
2. Python 3 and the [Block-n-Pick repository](https://github.com/DigiMancer3D/Block-n-Pick).
3. Enough disk space for the source corpus and the reconstructed image.
4. The `.bnpm` file downloaded from this directory.

Use a Block-n-Pick release compatible with the recipe format. The project is under active development, so check its README and format documentation for version-specific details.

### CLI workflow

From a local checkout of Block-n-Pick:

```bash
git clone https://github.com/DigiMancer3D/Block-n-Pick.git
cd Block-n-Pick

# Optional but recommended: inspect/resolve the recipe first.
python run_bnp.py resolve "/path/to/3D Close Up_bnp.bnpm"

# Build the image and verify its declared identity.
python run_bnp.py mine "/path/to/3D Close Up_bnp.bnpm" \
  --action build-verify --out-dir ./reconstructed
```

Before running `mine`, make sure Block-n-Pick has access to your local BTC source. Depending on the version and setup, that means configuring or acquiring a local corpus from the node first; follow [Block-n-Pick's acquisition documentation](https://github.com/DigiMancer3D/Block-n-Pick/blob/main/docs/ACQUISITION.md). The project prioritizes an existing local BnP corpus and local node/daemon data before public providers. For a fully local workflow, do not fall back to public providers.

You can also verify without writing an output file:

```bash
python run_bnp.py mine "/path/to/sticker.bnpm" --action verify
```

A successful `build-verify` writes the reconstructed output into the directory supplied with `--out-dir` and checks its RAW and canonical Base64 SHA-256 identities. Existing target files are not overwritten; incomplete `.part` files are cleaned up if construction is cancelled. See [MINE_BUILDING.md](https://github.com/DigiMancer3D/Block-n-Pick/blob/main/docs/MINE_BUILDING.md) for the construction and safety details.

### GUI workflow

If you prefer a graphical workflow, install/run Block-n-Pick with its documented GUI launcher, configure a local BTC source or corpus, then use **Mine / Resolve** to open the `.bnpm` recipe and choose **Build + Verify**. The GUI and CLI use the same recipe-resolution and verification concepts.

### If reconstruction fails

- Confirm the recipe was downloaded intact and still has the `.bnpm` extension.
- Confirm your local BTC data covers the blocks referenced by the recipe.
- Run `resolve` first to identify missing sources or format problems.
- Use `--no-corpus` only when you intentionally want to bypass the local corpus; it may require another configured source.
- Compare the Block-n-Pick version and documentation with the recipe's format.
- Share the error and recipe filename when asking for help—never share wallet keys or other private node credentials.

## Sharing and remixing

- Download the image that fits your use case.
- Keep the 3DCP name visible where practical.
- Tag posts with **#3DCP** and credit **3D Changes Perspectives**.
- For alternate crops, captions, translations, or accessibility improvements, open an issue or pull request with context about the change.

Have fun, be thoughtful with references, and keep changing perspectives.

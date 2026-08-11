# agent_skills/asset_qa — reviewing imported and generated 3D content

Skills for a **vision-capable** agent, covering the two questions about a
3D asset that no amount of code can answer.

| File | Question | Answered by |
|---|---|---|
| `imported_asset_orientation.md` | Which way does this model face, and how big is it meant to be? | Looking at rendered views |
| `generated_asset_review.md` | Is this generated mesh fit to ship? | Looking at rendered views |

Both are driven by one adapter operation:

```python
report = three.preview.orientation_report("<asset_id>")
report["payload"]["contact_sheet"]   # one labelled image, five views
```

It renders on the CPU with `numpy` and `Pillow` — no GPU, no display, no
browser — so a review costs about two seconds per asset and runs anywhere
the rest of the pipeline runs.

## Why these are skills and not code

Everything a program can decide about an asset has already been decided
before these skills run: the adapter validates the format, reads the node
hierarchy, counts triangles, measures the bounding box, and narrows the
facing axis to the two signs of the shallow horizontal axis.

What is left is genuinely undecidable without sight. A model facing +Z and
the same model facing -Z have identical files in every respect a parser
can reach. A mesh whose unseen back reconstructed as a smear has a
perfectly valid node tree. These are the questions a vision model should
be asked, and they are the only ones in this directory.

## Where the answers go

Into the artifact record, and from there into
`public/assets/manifest.json`:

```python
three.assets.set_orientation(
    "<asset_id>", forward_axis="+z", scale_hint_metres=1.8,
    verified_by="agent_vision", notes="...",
)
```

The runtime applies whatever is recorded and leaves an unrecorded asset
exactly as authored, so annotating an asset can never make an
already-correct game worse. Recording the fact once beats correcting it in
every game that uses the asset — which is also why fixing a rotation
inside gameplay code is explicitly a mistake.

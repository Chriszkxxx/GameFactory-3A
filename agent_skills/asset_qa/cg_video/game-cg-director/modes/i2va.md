# I2VA

Use only when one image is explicitly the first frame.

- Set `mode` to `first_frame_to_video` and put its path in `first_frame_path`.
- Treat the supplied image as the exact 0.00-second state of the opening shot.
- Preserve only inspected or user-declared facts. If the frame is opaque, anchor it neutrally and do not enumerate unseen attributes.
- From an inspected frame, keep only motion-relevant anchors: primary subjects, foreground/background placement, key objects, light, and spatial relationships. Do not inventory minor decoration that does not affect the requested change.
- If the requested motion depends on an unconfirmed visible subject, ask which subject to animate or follow before writing.
- Use: first-frame anchor → action onset → continuous development → visible result or reaction.
- For a requested focus shift, keep the camera static unless camera travel is also requested; name what starts sharp, how focus changes, and what ends sharp.
- Prefer one continuous shot for a short clip. Add a cut only when the user requests it or the cut is necessary to show new information.
- Follow the selected model profile for first-frame labels, binding instructions, and prompt placement.
- Do not add a last-frame or reference-array field.

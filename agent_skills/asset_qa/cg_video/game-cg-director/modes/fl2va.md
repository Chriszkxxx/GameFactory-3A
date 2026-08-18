# FL2VA

Use only when two images are explicitly the first and last frames.

- Set `mode` to `first_last_frame_to_video`; put paths in `first_frame_path` and `last_frame_path`.
- Treat the first image as the exact 0.00-second state and the last image as the exact state at `duration_sec`.
- Establish endpoints only from inspection or sufficient user descriptions. Ask when an opaque endpoint lacks facts necessary for the transition.
- Describe the reachable path through subject motion, pose change, object handling, composition change, and requested light or scene transitions.
- Prefer one continuous shot. Use multiple shots only when explicitly requested or when the endpoints require them.
- Progressively narrow visible differences until the final frame; do not merely describe two static images.
- Follow the selected model profile for endpoint labels, alignment instructions, and prompt placement.

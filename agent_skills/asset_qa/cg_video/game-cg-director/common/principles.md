# Prompt principles

## Observable scope

- Describe only visible, audible, or timed events. Express emotion through posture, facial action, movement, light, speech, or sound.
- Keep the selected game purpose observable: an opening establishes the world, a cutscene changes the playable situation, an ultimate demonstrates a signature ability and its requested outcome, and a promo demonstrates a feature or fantasy. Do not flatten it into a generic film montage.
- State subject, environment, action, and result in playback order. Preserve user-supplied dialogue, lyrics, and visible text verbatim.
- Give every supplied reference a declared responsibility. Use only inspected facts or the user's explicit description; never infer content from a path or filename.
- Keep references opaque when their contents are unavailable. Ask only when an unverified fact is necessary to plan the requested motion or endpoint.
- In text-only gaps, add only the generic actor, vehicle, object, or action needed for a named setting or activity. Place it by scene purpose, readability, continuity, and time. Keep identity, brand, and plot unspecified; state an exact count only when action or cross-shot continuity depends on it.
- Replace named-game shorthand with the executable style mapping when available. Do not add story, weather, effects, or camera behavior from style alone.

## Storyboard and performance

- Build coverage from the current visual tasks, not a prior example, fixed shot count, or automatic wide-to-close sequence. Give each shot one purpose and visual priority. Describe an intermediate result only if the next shot inherits it; always show the final result. Keep later cut times precise, increasing, and inside the duration using model notation.
- Across a cut, preserve location, identity, facing direction, carried motion, and changed world state unless the user requests a discontinuity. Cut only when the next shot adds information; use camera movement for a smaller change.
- Keep the gameplay relationship readable—actor, goal or threat, action, and result. Fit the chain inside `duration_sec` and leave the result or reaction visible.
- Make intention and effort visible through relevant gaze, body orientation, weight shift, facial action, hand or prop use, and voice delivery. Stage performance as preparation → action → interaction or reaction when needed → recovery or held result. Keep simultaneous actions anatomically compatible and give dialogue a readable speaking beat.
- Express spatial and causal constraints positively: state where the actor and camera are, what direction they face or move, and what changes. Do not grow a list of unrelated failure prohibitions.

Compact shot order: composition and subject → visible action → camera action → synchronized sound → resulting state.

Reject plot-only summaries, overcrowded short shots, invalid cut times, changing reference roles, static keyframe descriptions with no transition path, and provider or metadata text in the prompt.

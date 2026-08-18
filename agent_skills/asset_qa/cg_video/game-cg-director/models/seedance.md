# Seedance model profile

```json machine-checks
{"model":"seedance"}
```

## Contract

- Write `prompt` as English natural-language direction. Preserve user-supplied
  dialogue, lyrics, and visible text verbatim.
- Keep duration, ratio, resolution, seed, audio enablement, and other API
  controls out of the prose; the Harness passes them as request parameters.
- Do not use H3 section names, XML-like dialogue tags, picture-alignment
  declarations, or retention markers. They are not Seedance syntax.
- Do not state a duration or reference-count limit here unless it is verified
  for the exact deployed model version and task type.

## Prompt composition

Use this order, omitting parts that do not affect the requested clip:

```text
<subject and scene anchor> + <observable action> + <environment and light> +
<camera and edit> + <visual style> + <sound> + <necessary constraints>
```

- Define each recurring subject with two or three stable, visible traits, then
  reuse one unambiguous name. Do not redesign it after a cut.
- Replace abstract emotion or mood with visible performance: pose, gaze,
  expression, breathing, speed, force, and reaction.
- Describe actions as a causal sequence, including the physical transition
  between start and result. Prefer a few readable actions over simultaneous
  competing events.
- Use standard shot language such as wide shot, close-up, fixed camera, dolly,
  pan, tracking, or cut. Give one shot one dominant camera movement.
- State only constraints that protect acceptance criteria, such as stable
  identity, preserved composition, no subtitles, or no logo. Avoid long
  generic negative-prompt lists and conflicting adjectives.

## Sequential shots

Use one paragraph for a simple continuous shot. For a clip that requires cuts,
write short blocks in playback order:

```text
Overall: <stable cast, setting, visual treatment, and continuity anchors>.
Shot 1: <framing or camera> + <subject action> + <spatial change> + <sound>.
Shot 2: <cut or camera> + <subject action and result> + <sound>.
Constraints: <only the constraints needed for this task>.
```

- Number shots sequentially and keep each shot focused on new information.
- Do not assign exact timestamp ranges by default. Use timing only when a user
  requires synchronization; otherwise express order and rhythm with words such
  as `first`, `then`, `as`, `after`, and `finally`.
- Put a sound effect, line, or music change in the shot where it is heard.
  Name the source, onset, intensity, and audible change when they matter.

## Reference binding

Number references by their input order and bind every reference to one explicit
responsibility. Use the API-style tokens `@Image N`, `@Video N`, and `@Audio N`
when those materials are present; do not use a file name or asset ID as a
prompt-side substitute.

- Subject reference: `Use the red-armored pilot in @Image 1 as the player;
  preserve the helmet silhouette and chest emblem.`
- Attribute transfer: `Use only the lighting and color palette of @Image 2;
  do not copy its subject, pose, or composition.`
- Motion or camera reference: `Follow the camera movement of @Video 1 while
  keeping the player and arena defined above.`
- Audio reference: `Match the percussion rhythm of @Audio 1; synchronize the
  impact accent with the final strike.`

For multiple subjects, define each once before the shot blocks, then use the
same name in every later action. A reference must not silently supply unrelated
identity, background, pose, camera, style, and sound responsibilities.

### Mode wording

- T2VA: begin directly with the subject, setting, and opening composition; use
  no reference token.
- I2VA: say `Use the supplied first frame as the exact opening composition`,
  identify what begins moving, and preserve all unmentioned visible elements.
- FL2VA: say `Begin from the supplied first frame and end at the supplied last
  frame`, then describe a physically reachable transition rather than two
  disconnected endpoint descriptions.
- Ref2VA: define reference roles first, then state the shot or event where each
  role takes effect.

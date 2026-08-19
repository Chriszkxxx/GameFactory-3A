# Style mapping

- Match one row and adapt its fragment to the scene. Do not add camera, action, sound, weather, story, or effects from style alone.
- A style reference overrides shorthand. Unknown named styles require visible traits or a reference; do not guess.
- `cinematic`, `8K`, and engine names are insufficient alone. Do not stack styles without user priorities.

| Triggers | Executable prompt fragment | Do not add unless requested or referenced |
| --- | --- | --- |
| 3D game CG, AAA game CG, open-world game CG | Detailed 3D game CG; readable environment geometry; consistent subject, clothing, and material appearance across shots. | Specific engine, photorealism, HUD, combat, effects |
| 8-bit, pixel game, retro pixel | 8-bit pixel-art game style with scanline effect; preserve the requested subject, action, and palette. | Console era, chiptune, fixed palette |
| anime film, anime movie, Japanese animation | 2D-animated anime-film style; consistent character design and colors; scene lighting keeps faces and actions readable. | Named studio, fixed palette, magic effects |
| live action, photoreal, shot on camera | Live-action photographed look; recognizable skin, fabric, metal, glass, and location surfaces under the requested light. | Film grain, lens, handheld motion, color grade |
| commercial, product ad, premium product video | Product-advertising style; product shape, controls, materials, and reflections remain readable. | Luxury styling, white studio, macro shot, text, logo |
| cyberpunk, cyberpunk city | Cyberpunk setting with visible high-tech infrastructure or body modification integrated into the built environment; inherit palette, weather, and time from the request or reference. | Automatic rain, night, cyan-magenta neon, holograms |
| GTA5 graphics, GTA-like | Detailed 3D open-world game CG with long-view depth and fine road and building textures; show dense readable traffic or pedestrians only when relevant. | Characters, crime, weapons, HUD, logos, missions |
| Genshin, Genshin-like | 3D anime-stylized game CG; clear character shading; stable costume colors and facial design; scene-specific natural landscape light. | Named region, fixed palette, magic, existing characters |
| watercolor, claymation, felt texture, illustration, vintage film | State the medium once; preserve the requested subject, composition, and palette; use supplied surface or film traits only. | Unrequested texture, jitter, scratches, monochrome, VHS, era |

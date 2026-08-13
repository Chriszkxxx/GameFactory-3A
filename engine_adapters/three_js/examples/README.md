# three.js Reference Gameplay Packages

These packages are optional concrete examples built on the public
`@a3game/playable` contract:

| Package | Demonstrates |
| --- | --- |
| `arena-fighter-example` | Third-person movement, light/heavy attacks, arena rules, health HUD |
| `fps-example` | Pointer-lock first-person movement, hitscan fire, reload, crosshair HUD |
| `racing-example` | Arcade vehicle steering, boost, handbrake drift, lap and speed HUD |
| `motion-vfx-example` | Getting motion onto a generated character, and batched particles, beams, and trails |

They are never installed automatically. Generated games should adapt the
relevant patterns inside their own Gameplay Package rather than depending
on or extending an example package.

`motion-vfx-example` is the odd one out: it contains no game, only the two
patterns that every genre needs and that are easy to get wrong —
`assets.tryInstantiate` is correct for a downloaded character and silently
wrong for a generated one, which has no skeleton and no clips, and one
`Sprite` per spark is one draw call per spark. Read it before writing an
entity that swaps in imported art or an effect of any kind.

Each example owns its concrete entity classes, entity factory, rules, and
HUD. `@a3game/playable` owns only normalized input, session, binding,
entity, world, and observation contracts.

## Reading order

1. `src/entity.js` - how a concrete entity implements
   `A3GameControllableEntity` and turns a normalized input frame into
   movement.
2. `src/factory.js` - how an entity factory loads artifacts through
   `A3GameAssetLibrary` and returns a controllable entity.
3. `src/index.js` - how the game boots: world load, HUD, input router,
   factory registration.
4. `tests/` - how a generated game proves it works, using the local
   runtime bridge instead of screenshots.

## Installing one as a starting point

```python
from engine_adapters.three_js import ThreeClient

three = ThreeClient(project_path="/path/to/project")
three.plugin.install(
    {
        "game_id": "my_game",
        "run_id": "default",
        "task_kind": "mechanic",
        "task_id": "gameplay_package",
    }
)
```

`plugin.install` consumes a repository task identity, not a path inside
this directory. Copying an example by hand bypasses the registry and the
dependency synchronization that `plugin.install` performs.

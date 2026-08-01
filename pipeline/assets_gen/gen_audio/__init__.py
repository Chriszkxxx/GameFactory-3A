"""Audio asset-generation pipeline.

Future ``run.py`` will generate one audio artifact per task and ``eval.py``
will evaluate it using ``operators.gen_audio.metrics``. Both entry points are
intentionally deferred while the task contract and model backends are designed.
"""

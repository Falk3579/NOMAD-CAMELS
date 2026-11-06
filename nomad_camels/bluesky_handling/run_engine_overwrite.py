from bluesky import run_engine, RunEngine
import logging


def get_nan_value(value):
    """
    Returns a NaN value of the same type as the input value.
    For example:
    If the input value is a numpy array, it returns an array of NaNs with the same shape.
    If the input value is a list, it returns a list of NaNs with the same length.
    If the input value is a dictionary, it returns an empty dictionary.
    """
    import numpy as np

    if isinstance(value, np.ndarray):
        return np.full(value.shape, np.nan)
    if isinstance(value, (int, float, np.number)):
        return np.nan
    if isinstance(value, str):
        return ""
    if isinstance(value, list):
        return [np.nan] * len(value)
    if isinstance(value, dict):
        return {}
    if isinstance(value, tuple):
        return tuple([np.nan] * len(value))
    if isinstance(value, set):
        return set()
    if isinstance(value, bool):
        return False
    if isinstance(value, complex):
        return np.nan
    return None


class RunEngineOverwrite(RunEngine):
    """
    A class that overwrites the `RunEngine` class from bluesky to add a custom read method.
    This class is used to handle the reading of objects in a more robust way, especially when dealing with exceptions. It allows to keep running the run engine even if an object raises an exception during the read process.
    """

    async def _read(self, msg):
        """Read one or more devices while preserving CAMELS' error recovery.

        Bluesky 1.16 treats every positional object in a read message as a
        device and passes a list of (device, reading) pairs to the bundler.
        The previous CAMELS override passed the reading dict itself, which
        now causes ValueError during normal measurement plans.
        """
        import asyncio
        import time

        objects = list((msg.obj,) + msg.args) if msg.obj is not None else []
        objects = [
            run_engine.check_supports(obj, run_engine.Readable) for obj in objects
        ]

        async def read_one(obj):
            try:
                return await self._perform_single_reading(obj)
            except Exception as exc:
                if not getattr(obj, "__read_w_except__", False):
                    raise
                logging.warning("Error reading object %s: %s", obj, exc)
                return {
                    obj.name: {
                        "value": get_nan_value(getattr(obj, "value", None)),
                        "timestamp": time.time(),
                    }
                }

        readings = await asyncio.gather(*(read_one(obj) for obj in objects))
        current_run = self._run_bundlers.get(msg.run)
        if current_run is not None:
            await current_run.read(msg, list(zip(objects, readings)))

        result = {}
        for reading in readings:
            result.update(reading)
        return result

from bluesky import run_engine, RunEngine
import logging
import time


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

    @staticmethod
    def _skipped_reading(obj, error):
        """Return a placeholder reading when a device read may be skipped."""
        logging.warning("Error reading object: %s, Exception: %s", obj, error)
        print("Error reading object: ", obj)
        print("Exception: ", error)
        return {
            obj.name: {
                "value": get_nan_value(obj.value),
                "timestamp": time.time(),
            }
        }

    async def _perform_single_reading(self, obj, *read_args, **read_kwargs):
        """Handle optional read failures using the newer Bluesky read hook.

        Recent Bluesky versions use this hook to gather individual readings
        and pass (object, reading) pairs to the run bundler.  Let the parent
        RunEngine handle normal reads and catch only explicitly skippable
        device read failures.
        """
        if not getattr(obj, "__read_w_except__", False):
            return await super()._perform_single_reading(
                obj, *read_args, **read_kwargs
            )

        try:
            ret = await run_engine.maybe_await(obj.read(*read_args, **read_kwargs))
        except Exception as error:
            ret = self._skipped_reading(obj, error)

        if ret is None:
            raise RuntimeError(
                f"The read of {obj.name} returned None. "
                "This is a bug in your object implementation, "
                "`read` must return a dictionary."
            )
        return ret

    async def _read(self, msg):
        # Newer Bluesky versions support multiple objects in a single read
        # message and expect (object, reading) pairs at the bundler boundary.
        # Delegate this protocol to upstream rather than duplicating it here.
        # Older supported Bluesky versions have no single-reading hook and
        # retain the original dictionary-based bundler interface below.
        if hasattr(RunEngine, "_perform_single_reading"):
            return await super()._read(msg)

        obj = run_engine.check_supports(msg.obj, run_engine.Readable)
        # actually _read_ the object
        run_engine.warn_if_msg_args_or_kwargs(msg, obj.read, msg.args, msg.kwargs)
        # the try except block is added
        if hasattr(obj, "__read_w_except__") and obj.__read_w_except__:
            try:
                ret = await run_engine.maybe_await(obj.read(*msg.args, **msg.kwargs))
            except Exception as error:
                ret = self._skipped_reading(obj, error)
        else:
            ret = await run_engine.maybe_await(obj.read(*msg.args, **msg.kwargs))

        if ret is None:
            raise RuntimeError(
                f"The read of {obj.name} returned None. "
                "This is a bug in your object implementation, "
                "`read` must return a dictionary."
            )
        run_key = msg.run
        try:
            current_run = self._run_bundlers[run_key]
        except KeyError:
            ...
        else:
            await current_run.read(msg, ret)

        return ret

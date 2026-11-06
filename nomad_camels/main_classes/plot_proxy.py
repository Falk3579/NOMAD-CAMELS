import zmq
import multiprocessing

def run_zmq_proxy(queue: multiprocessing.Queue):
    """
    Binds to port 0 (OS picks a free port) and returns the chosen ports
    via the queue.
    """
    context = zmq.Context.instance()
    frontend = context.socket(zmq.SUB)
    backend = context.socket(zmq.PUB)
    
    # Binding to port 0 lets the OS pick an available port
    in_port = frontend.bind_to_random_port("tcp://*")
    out_port = backend.bind_to_random_port("tcp://*")
    
    frontend.setsockopt_string(zmq.SUBSCRIBE, "")
    
    # Send the chosen ports back to the main process
    queue.put((in_port, out_port))
    
    try:
        zmq.proxy(frontend, backend)
    except Exception:
        pass
    finally:
        frontend.close()
        backend.close()
        context.term()


def run_remote_dispatcher(dispatcher):
    """Run Bluesky's ZMQ dispatcher and handle expected stop cancellation.

    RemoteDispatcher.stop() cancels its polling task. In Bluesky 1.16
    dispatcher.start() propagates that asyncio.CancelledError *after* its
    cleanup handler closes the loop and sockets. Normal shutdown should not
    produce an unhandled traceback in a background thread.
    """
    import asyncio

    try:
        dispatcher.start()
    except asyncio.CancelledError:
        if not dispatcher.closed:
            raise

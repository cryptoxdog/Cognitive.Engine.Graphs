"""Action-to-node resolution for the L9 Constellation Runtime."""
from constellation.types import SNAKE, ConstellationError

ACTION_MAP: dict[str, str] = {}
_HANDLERS: dict[str, callable] = {}

def register_action(action_name: str, node_name_or_handler=None):
    """Register an action. Usable as decorator or direct call."""
    if not SNAKE.match(action_name):
        raise ConstellationError(f"Action name must be snake_case: {action_name}")
    if action_name in ACTION_MAP:
        raise ConstellationError(f"Duplicate action: {action_name}")

    def _register(handler, node_name: str):
        ACTION_MAP[action_name] = node_name
        _HANDLERS[action_name] = handler

    if callable(node_name_or_handler):
        fn = node_name_or_handler
        _register(fn, getattr(fn, "_node_name", fn.__qualname__.split(".")[0]))
        return fn
    elif isinstance(node_name_or_handler, str):
        ACTION_MAP[action_name] = node_name_or_handler
        return None
    else:
        def decorator(fn):
            _register(fn, getattr(fn, "_node_name", fn.__qualname__.split(".")[0]))
            return fn
        return decorator

def get_action_handler(action_name: str):
    if action_name not in _HANDLERS:
        raise ConstellationError(f"Unknown action: {action_name}", status="rejected")
    return _HANDLERS[action_name]

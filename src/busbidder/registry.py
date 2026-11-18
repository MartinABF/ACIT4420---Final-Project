from busbidder.errors import ConfigError


class Registry:
    def __init__(self, kind):
        self.kind = kind
        self._items = {}

    def register(self, name):
        def decorator(item):
            if name in self._items:
                raise ConfigError(f"duplicate {self.kind}: {name}")
            self._items[name] = item
            return item

        return decorator

    def __getitem__(self, name):
        if name not in self._items:
            raise ConfigError(f"unknown {self.kind}: {name}")
        return self._items[name]

    def __iter__(self):
        return iter(self._items)

    def items(self):
        return self._items.items()

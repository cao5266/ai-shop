from .platform import PlatformAdapter
from .generic import GenericAdapter, DujiaoAdapter
from .catfk import CatfkAdapter
from .public_api import NextAdapter, YiciAdapter

ADAPTERS = {"16688": PlatformAdapter, "catfk": CatfkAdapter, "generic": GenericAdapter,
            "dujiao": DujiaoAdapter, "next": NextAdapter, "yici": YiciAdapter}

import logging

log = logging.getLogger(__name__)

from .core import *
from .config import *
from .logging import *

log.info("Initializing core systems.")
from .database import *
from .timing import *
from .emoji import *
from .serialization import *
from .settings import *

log.info("Initializing bot.")
from .bot import *

log.info("Initializing secondary systems.")
from .scoreboards import *

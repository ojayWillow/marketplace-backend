"""Task routes package.

This package organizes task-related routes into logical submodules:
- crud: Basic task operations (list, get, create, update)
- applications: Job application system (apply, accept, reject, withdraw)
- workflow: Task lifecycle (mark-done, confirm, dispute, cancel)
- helpers: Shared utilities (distance calc, translation, etc.)
"""

from flask import Blueprint

tasks_bp = Blueprint('tasks', __name__)

# Import helpers first (used by other modules)
from app.routes.tasks.helpers import (
    get_bounding_box,
    distance,
    translate_task_if_needed,
    get_pending_applications_count
)

# Import and register all route modules
from app.routes.tasks import crud
from app.routes.tasks import applications
from app.routes.tasks import workflow
from app.routes.tasks import queries

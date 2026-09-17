from pydantic import BaseModel


class CurrentPrincipal(BaseModel):
    """Authenticated identity: who is calling, and in which project scope."""

    user_id: str
    project_id: str

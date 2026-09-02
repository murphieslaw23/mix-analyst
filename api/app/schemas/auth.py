from pydantic import BaseModel


class CurrentPrincipal(BaseModel):
    """The authenticated user and project selected by a bearer token."""

    user_id: str
    project_id: str

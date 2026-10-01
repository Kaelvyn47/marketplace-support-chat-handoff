from fastapi import FastAPI

from marketplace_chat.models import SupportSessionRequest, SupportSessionResponse
from marketplace_chat.support_handoff import SupportHandoffService

app = FastAPI(title="Marketplace support chat")
service = SupportHandoffService.from_env()


@app.post("/support-sessions", response_model=SupportSessionResponse)
def create_support_session(request: SupportSessionRequest) -> SupportSessionResponse:
    return service.open_session(request)

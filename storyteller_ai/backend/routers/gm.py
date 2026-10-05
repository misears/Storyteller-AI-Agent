from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..models.campaign import Actor
from ..services.campaign_service import campaign_service
from ..services.campaign_turn_service import campaign_turn_service, TurnConflictError
from ..services.llm_client import LLMTimeoutError, OllamaConnectionError
from ..engines.gm_loop import ToolLoopLimitError

router = APIRouter(prefix="/gm", tags=["gm"])


class GMStepRequest(BaseModel):
    session_id: str
    message: str
    client_msg_id: str | None = None


@router.post("/step")
async def gm_step(payload: GMStepRequest):
    campaign = campaign_service.get(payload.session_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        return await campaign_turn_service.submit(
            campaign,
            payload.message,
            Actor(kind="player"),
            client_msg_id=payload.client_msg_id,
        )
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except OllamaConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TurnConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ToolLoopLimitError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

"""Trip planning API routes."""

import os

from fastapi import APIRouter, HTTPException

from ...agents.trip_planner_agent import MultiAgentTripPlanner, get_trip_planner_agent
from ...models.schemas import TripPlanResponse, TripRequest

router = APIRouter(prefix="/trip", tags=["trip-planner"])


@router.post(
    "/plan",
    response_model=TripPlanResponse,
    summary="Generate trip plan",
    description="Generate a trip plan from city, dates, transport, accommodation, and preferences.",
)
async def plan_trip(request: TripRequest):
    """Generate a trip plan.

    TRIP_FAST_MODE=true, default:
        Skip LLM calls and build a demo plan from AMap Web API or curated city POIs.

    TRIP_FAST_MODE=false:
        Use the original HelloAgents multi-agent workflow with LLM and MCP tools.
    """
    try:
        print("\n" + "=" * 60)
        print("Received trip planning request:")
        print(f"   city: {request.city}")
        print(f"   dates: {request.start_date} - {request.end_date}")
        print(f"   days: {request.travel_days}")
        print("=" * 60 + "\n")

        if os.getenv("TRIP_FAST_MODE", "true").lower() != "false":
            print("FAST_MODE enabled: skip LLM and generate a test plan directly.")
            planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
            trip_plan = planner._create_amap_direct_plan(request)
            if trip_plan is None:
                trip_plan = planner._create_fallback_plan(request)
        else:
            print("LLM_MODE enabled: use HelloAgents multi-agent workflow.")
            agent = get_trip_planner_agent()
            trip_plan = agent.plan_trip(request)

        return TripPlanResponse(
            success=True,
            message="Trip plan generated successfully",
            data=trip_plan,
        )

    except Exception as exc:
        print(f"Failed to generate trip plan: {exc}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate trip plan: {exc}")


@router.get(
    "/health",
    summary="Trip service health check",
    description="Check whether the trip planning service can be initialized.",
)
async def health_check():
    """Health check."""
    try:
        if os.getenv("TRIP_FAST_MODE", "true").lower() != "false":
            return {
                "status": "healthy",
                "service": "trip-planner",
                "mode": "fast",
                "llm_enabled": False,
            }

        agent = get_trip_planner_agent()
        return {
            "status": "healthy",
            "service": "trip-planner",
            "mode": "llm",
            "llm_enabled": True,
            "tools_count": len(agent.attraction_agent.list_tools()),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {exc}")

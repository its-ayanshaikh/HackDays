"""Django views for AskMyData."""

import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from . import agent, analytics
from .llm import active_provider
from .schema import SAMPLE_QUESTIONS
from .snowflake_client import SnowflakeError, test_connection


@require_GET
def index(request):
    """Render the single-page dashboard shell."""
    return render(request, "core/index.html", {"samples": SAMPLE_QUESTIONS})


@require_POST
def ask(request):
    """Run the agentic pipeline for a natural-language question."""
    try:
        payload = json.loads(request.body.decode("utf-8"))
        question = payload.get("question", "")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "Invalid request body."}, status=400)

    return JsonResponse(agent.run_pipeline(question))


@require_GET
def dashboard(request):
    return JsonResponse(analytics.dashboard())


@require_GET
def tables(request):
    return JsonResponse(analytics.table_list())


@require_GET
def table_preview(request, name):
    return JsonResponse(analytics.table_preview(name))


@require_GET
def nations(request):
    return JsonResponse(analytics.nations())


@require_GET
def focus(request, nation):
    return JsonResponse(analytics.market_focus(nation))


@require_GET
def anomaly_radar(request):
    """Run the cached Snowflake-native anomaly scan and AI investigation."""
    return JsonResponse(analytics.anomaly_radar())


@require_GET
def health(request):
    """Snowflake connectivity + active LLM provider (for the Settings page)."""
    info = {"provider": active_provider()}
    try:
        info.update(test_connection())
    except SnowflakeError as exc:
        info.update({"ok": False, "error": str(exc)})
    return JsonResponse(info)

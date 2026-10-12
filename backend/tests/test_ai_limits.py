"""Faixas gratuitas de IA: teto por minuto, 429 com espera e cota do dia."""

import json
from types import SimpleNamespace

import httpx
import pytest

from revalli.core.config import get_settings
from revalli.modules.ai import client
from revalli.modules.ai.client import AIError, Endpoint

OK = {
    "choices": [{"message": {"content": "{}"}}],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
}
MSG = [{"role": "user", "content": "oi"}]


@pytest.fixture(autouse=True)
def _reset():
    client.reset_throttle()
    yield
    client.set_transport(None)
    client.reset_throttle()


def _use(handler):
    client.set_transport(httpx.MockTransport(handler))


async def test_429_per_minute_is_retried_then_succeeds():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, json={"error": {"message": "Rate limit reached"}})
        return httpx.Response(200, json=OK)

    _use(handler)
    result = await client.chat(Endpoint("http://x/v1", "", "m"), MSG)
    assert result.content == "{}" and len(calls) == 3


async def test_persistent_429_becomes_rate_limited():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, text="slow down")

    _use(handler)
    with pytest.raises(AIError, match="rate_limited"):
        await client.chat(Endpoint("http://x/v1", "", "m"), MSG)
    assert len(calls) == client.MAX_RETRIES + 1


async def test_daily_quota_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(
            429, text='{"error": "Rate limit reached: tokens per day (TPD): Limit 500000"}'
        )

    _use(handler)
    with pytest.raises(AIError, match="quota_exhausted"):
        await client.chat(Endpoint("http://x/v1", "", "m"), MSG)
    assert len(calls) == 1


async def test_json_mode_refused_falls_back_without_response_format():
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        if "response_format" in body:
            return httpx.Response(400, text="response_format is not supported by this model")
        return httpx.Response(200, json=OK)

    _use(handler)
    result = await client.chat(Endpoint("http://x/v1", "", "m"), MSG)
    assert result.content == "{}"
    assert "response_format" in bodies[0] and "response_format" not in bodies[1]


async def test_requests_are_spaced_by_the_provider_limit(monkeypatch):
    monkeypatch.setattr(get_settings(), "api_delay_seconds", 0.35)
    now = [1000.0]
    slept: list[float] = []

    async def fake_sleep(seconds):
        slept.append(round(seconds, 2))
        now[0] += seconds

    monkeypatch.setattr(client, "asyncio", SimpleNamespace(sleep=fake_sleep))
    monkeypatch.setattr(client, "time", SimpleNamespace(monotonic=lambda: now[0]))
    _use(lambda request: httpx.Response(200, json=OK))
    ep = Endpoint("http://x/v1", "", "m", rpm=30)  # um pedido a cada 2 s
    for _ in range(3):
        await client.chat(ep, MSG)
    # O primeiro passa na hora; os dois seguintes esperam o intervalo inteiro
    assert slept == [2.0, 2.0]


async def test_provider_rpm_limit_roundtrip(admin):
    r = await admin.post(
        "/api/ai/providers",
        json={
            "name": "Groq",
            "kind": "groq",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key": "gsk_test1234",
            "rpm_limit": 25,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "groq" and r.json()["rpm_limit"] == 25
    r = await admin.put(
        f"/api/ai/providers/{r.json()['id']}",
        json={"name": "Groq", "kind": "groq", "base_url": "https://api.groq.com/openai/v1"},
    )
    assert r.json()["rpm_limit"] is None
    bad = await admin.post(
        "/api/ai/providers",
        json={"name": "x", "kind": "custom", "base_url": "http://x/v1", "rpm_limit": 0},
    )
    assert bad.status_code == 422

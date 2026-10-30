"""Native Jev adapter: reuse the application client in an evaluation interface."""

from typesafe_sdk import AsyncTypeSafeClient, Noul


async def is_billing_message(client: AsyncTypeSafeClient, text: str) -> float:
    result = await client.system_one(
        state=text,
        questions={"billing": Noul(instructions="Is this message about billing?")},
    )
    return result.raw_http_response.json()["answers"]["billing"]["noul"]

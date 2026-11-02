"""Fake camera and AI Task for the Home Assistant runtime tests.

Nothing here reaches a real camera, Gemini or an AC.
"""

from pathlib import Path

from homeassistant.components.ai_task import AITaskEntity, AITaskEntityFeature, GenDataTaskResult
from homeassistant.components.camera import Camera
from homeassistant.exceptions import HomeAssistantError


class FakeCamera(Camera):
    def __init__(self, floor="2nd"):
        super().__init__()
        self.entity_id = f"camera.{floor}_floor"
        self._attr_unique_id = f"fake_{floor}_floor"
        self._attr_name = f"{floor} Floor"

    async def async_camera_image(self, width=None, height=None):
        # Not a staff image: a 1x1 JPEG. The AI fake only checks that the file exists.
        return bytes.fromhex(
            "ffd8ffe000104a46494600010100000100010000ffdb004300"
            + "08" * 64
            + "ffc00011080001000103012200021101031101ffc40014000100000000000000000000000000000000"
            + "ffc40014100100000000000000000000000000000000ffda000c03010002110311003f00ffd9"
        )


class FakeAI(AITaskEntity):
    """Returns scripted answers from `answers`; an exception in the list is raised.
    With no answer left it behaves like a failed Gemini call."""

    _attr_supported_features = AITaskEntityFeature.GENERATE_DATA | AITaskEntityFeature.SUPPORT_ATTACHMENTS

    def __init__(self):
        self.entity_id = "ai_task.google_ai_task"
        self._attr_unique_id = "fake_google_ai_task"
        self._attr_name = "Google AI Task"
        self.answers = []
        self.calls = 0

    async def _async_generate_data(self, task, chat_log):
        self.calls += 1
        assert task.attachments and Path(task.attachments[0].path).exists()
        if not self.answers:
            raise HomeAssistantError("no scripted answer")
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return GenDataTaskResult(conversation_id=chat_log.conversation_id,
                                 data=task.structure(answer))

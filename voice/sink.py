from collections import defaultdict

from discord.sinks import Sink


class UserAudioSink(Sink):
    """Captures a rolling buffer of PCM audio per user (per SSRC).

    Pycord's PacketRouter decodes incoming Opus to 16-bit 48kHz stereo PCM and
    calls ``write(data, user)`` for each chunk.  We store it keyed by user_id and
    let the VAD layer decide when an utterance is complete.

    Note (py-cord 2.8+/DAVE rework): ``write`` now receives a ``VoiceData`` object
    (``data.pcm`` / ``data.source``) and ``user`` is a ``User``/``Member`` object
    (or ``None`` before the SSRC→user mapping resolves), not a bare int as in the
    old Sink API.  We normalize to an int user_id and skip unresolved packets.
    """

    def __init__(self):
        super().__init__()
        # user_id -> accumulated PCM bytes
        self._buffers: dict[int, bytearray] = defaultdict(bytearray)

    def write(self, data, user):
        # user may be an int (legacy), a User/Member object, or None (unresolved SSRC)
        if user is None:
            return
        user_id = user if isinstance(user, int) else getattr(user, "id", None)
        if user_id is None:
            return

        pcm = getattr(data, "pcm", None)
        if pcm is None:
            # Fallback for any path that still passes raw bytes
            pcm = data if isinstance(data, (bytes, bytearray)) else None
        if not pcm:
            return

        self._buffers[user_id].extend(pcm)

    def drain(self, user: int) -> bytes:
        """Return and clear the accumulated PCM for a user."""
        data = bytes(self._buffers[user])
        self._buffers[user].clear()
        return data

    def users_with_audio(self) -> list[int]:
        return [uid for uid, buf in self._buffers.items() if len(buf) > 0]

    def buffer_size(self, user: int) -> int:
        """Current number of buffered PCM bytes for a user."""
        return len(self._buffers[user])

    def cleanup(self):
        self._buffers.clear()

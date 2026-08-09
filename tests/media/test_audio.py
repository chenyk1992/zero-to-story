"""Tests for audio mixer."""
from __future__ import annotations

from lfo.media.audio import AudioMixRequest, AudioMixer, AudioTrack


class TestAudioMixer:
    def test_preserve_native_only(self) -> None:
        mixer = AudioMixer()
        req = AudioMixRequest(native_audio_present=True, native_audio_strategy="preserve")
        result = mixer.mix(req)
        assert result.success
        assert result.has_audio
        assert "native" in result.applied_tracks

    def test_mute_native(self) -> None:
        mixer = AudioMixer()
        req = AudioMixRequest(native_audio_present=True, native_audio_strategy="mute")
        result = mixer.mix(req)
        assert not result.has_audio

    def test_external_tracks(self) -> None:
        mixer = AudioMixer()
        req = AudioMixRequest(
            native_audio_present=False,
            tracks=[
                AudioTrack(asset_key="dialogue.mp3", role="dialogue"),
                AudioTrack(asset_key="bgm.mp3", role="music", duck_group="background"),
            ],
        )
        result = mixer.mix(req)
        assert result.success
        assert result.has_audio
        assert "dialogue.mp3" in result.applied_tracks

    def test_invalid_strategy(self) -> None:
        mixer = AudioMixer()
        req = AudioMixRequest(native_audio_strategy="invalid")
        result = mixer.mix(req)
        assert not result.success

    def test_duck_computation(self) -> None:
        mixer = AudioMixer()
        track = AudioTrack(asset_key="bgm.mp3", role="music", duck_group="background")
        assert mixer.compute_duck(track, foreground_present=True) == -12.0
        assert mixer.compute_duck(track, foreground_present=False) == 0.0

"""Tests for audio mixer."""

from __future__ import annotations

from lfo.media.audio import AudioMixer, AudioMixRequest, AudioTrack


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

    def test_loudness_master_keeps_requested_rate_and_peak_headroom(self) -> None:
        command = AudioMixer().build_command(
            AudioMixRequest(
                native_audio_present=True,
                target_loudness_db=-16.0,
                target_sample_rate=48000,
            ),
            "input.mp4",
            "output.mp4",
        )
        filter_complex = command[command.index("-filter_complex") + 1]
        assert "loudnorm=I=-16.0:TP=-1.5:LRA=11" in filter_complex
        assert "alimiter=limit=0.841395:level=false" in filter_complex
        assert filter_complex.endswith(",aresample=48000[outa]")

    def test_declared_duration_pads_short_tracks_and_removes_shortest(self) -> None:
        command = AudioMixer().build_command(
            AudioMixRequest(
                native_audio_present=False,
                tracks=[AudioTrack(asset_key="short.wav", role="music")],
                clip_duration_ms=5_000,
            ),
            "input.mp4",
            "output.mp4",
        )
        filter_complex = command[command.index("-filter_complex") + 1]
        assert "atrim=duration=5.000" in filter_complex
        assert "apad=whole_dur=5.000" in filter_complex
        assert "-shortest" not in command
        assert command[command.index("-t") + 1] == "5.000"

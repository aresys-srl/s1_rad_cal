# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Unit tests for thermal denoising"""

import numpy as np

from rad_cal.corrections.denoising import apply_denoising_correction

SWATH = "IW1"


def make_noise_vectors(shape, value):
    return np.full(shape, value, dtype=np.float64)


def run(
    monkeypatch,
    target,
    noise_value,
    scaling=1.0,
    swath=SWATH,
    azimuth_noise_vectors=None,
    range_noise_vectors=None,
    is_grd=False,
):
    """
    Patch get_noise_vectors, call apply_denoising_correction, return result.
    Centralises monkeypatching so individual tests stay focused on assertions.
    """
    monkeypatch.setattr(
        "rad_cal.corrections.denoising.get_noise_vectors",
        lambda **_kwargs: make_noise_vectors(target.shape, noise_value),
    )
    return apply_denoising_correction(
        target_area=target,
        swath=swath,
        azimuth_indexes=(0, target.shape[0]),
        range_indexes=(0, target.shape[1]),
        azimuth_noise_vectors=azimuth_noise_vectors,
        range_noise_vectors=range_noise_vectors or [],
        scaling_conversion=scaling,
        is_grd=is_grd,
    )


class TestPhasePreservation:
    def test_phase_preserved_signal_dominates_noise(self, monkeypatch):
        """When signal power >> noise, phase must be exactly preserved."""
        rng = np.random.default_rng(0)
        target = (rng.standard_normal((4, 8)) + 1j * rng.standard_normal((4, 8))).astype(np.complex64)
        result = run(monkeypatch, target, noise_value=0.01)
        nonzero = np.abs(result) > 0
        np.testing.assert_allclose(
            np.angle(result[nonzero]),
            np.angle(target[nonzero]),
            atol=1e-6,
        )

    def test_phase_preserved_arbitrary_phases(self, monkeypatch):
        phases = np.linspace(-np.pi, np.pi, 37, endpoint=False)
        amplitudes = np.full_like(phases, 5.0)
        target = (amplitudes * np.exp(1j * phases)).reshape(1, -1).astype(np.complex64)

        result = run(monkeypatch, target, noise_value=0.1)

        nonzero = np.abs(result) > 0
        np.testing.assert_allclose(
            np.angle(result[nonzero]),
            np.angle(target[nonzero]),
            atol=1e-6,
            err_msg="Phase changed for arbitrary-phase samples",
        )

    def test_phase_preserved_noise_partially_clips_amplitude(self, monkeypatch):
        """Even when noise substantially reduces magnitude, phase must be unchanged."""
        target = np.array([[2 + 0j, 0 + 2j, -2 + 0j, 0 - 2j]], dtype=np.complex64)
        result = run(monkeypatch, target, noise_value=3.0)

        nonzero = np.abs(result) > 0
        np.testing.assert_allclose(
            np.angle(result[nonzero]),
            np.angle(target[nonzero]),
            atol=1e-6,
            err_msg="Phase changed when noise partially clips amplitude",
        )

    def test_phase_preserved_mixed_quadrants(self, monkeypatch):
        """Samples in all four complex quadrants keep their phase."""
        target = np.array([[1 + 1j, -1 + 1j, -1 - 1j, 1 - 1j]], dtype=np.complex64)
        result = run(monkeypatch, target, noise_value=0.5)

        nonzero = np.abs(result) > 0
        np.testing.assert_allclose(
            np.angle(result[nonzero]),
            np.angle(target[nonzero]),
            atol=1e-6,
            err_msg="Phase changed in mixed-quadrant case",
        )

    def test_phase_preserved_with_nonunit_scaling(self, monkeypatch):
        """scaling_conversion ≠ 1 still yields no phase change."""
        rng = np.random.default_rng(42)
        target = (rng.standard_normal((5, 5)) + 1j * rng.standard_normal((5, 5))).astype(np.complex64) * 10
        result = run(monkeypatch, target, noise_value=0.01, scaling=2.0)

        nonzero = np.abs(result) > 0
        np.testing.assert_allclose(
            np.angle(result[nonzero]),
            np.angle(target[nonzero]),
            atol=1e-6,
            err_msg="Phase changed with non-unit scaling_conversion",
        )

    def test_phase_preserved_2d_array(self, monkeypatch):
        """Phase preservation holds for a realistic 2-D image patch."""
        rng = np.random.default_rng(7)
        target = (rng.standard_normal((64, 128)) + 1j * rng.standard_normal((64, 128))).astype(np.complex64)
        result = run(monkeypatch, target, noise_value=0.05)

        nonzero = np.abs(result) > 0
        np.testing.assert_allclose(
            np.angle(result[nonzero]),
            np.angle(target[nonzero]),
            atol=1e-6,
            err_msg="Phase changed in 2-D image patch",
        )


class TestAmplitudeBehaviour:
    def test_zero_noise_leaves_amplitude_unchanged(self, monkeypatch):
        """With zero noise the function is an identity."""
        target = np.array([[3 + 4j]], dtype=np.complex64)
        result = run(monkeypatch, target, noise_value=0.0)
        np.testing.assert_allclose(result, target, atol=1e-6)

    def test_output_magnitude_reduced_by_noise(self, monkeypatch):
        """Noise must reduce, never increase, the magnitude."""
        target = np.array([[3 + 4j]], dtype=np.complex64)  # power = 25
        result = run(monkeypatch, target, noise_value=9.0)  # corrected power = 16
        np.testing.assert_allclose(np.abs(result[0, 0]), 4.0, atol=1e-6)

    def test_power_exceeds_noise_exact_formula(self, monkeypatch):
        """Verify exact analytic value: |out| = sqrt(power - noise)."""
        amplitude, noise = 5.0, 9.0
        target = np.array([[amplitude + 0j]], dtype=np.complex64)
        result = run(monkeypatch, target, noise_value=noise)
        expected = np.sqrt(amplitude**2 - noise)  # sqrt(16) = 4
        np.testing.assert_allclose(np.abs(result[0, 0]), expected, atol=1e-6)


class TestClippingBehaviour:
    def test_noise_larger_than_power_outputs_zero(self, monkeypatch):
        """When noise > power the output must be exactly zero (no imaginary amplitude)."""
        target = np.array([[1 + 0j]], dtype=np.complex64)  # power = 1
        result = run(monkeypatch, target, noise_value=2.0)  # noise > power
        assert result[0, 0] == 0.0, "Expected zero output when noise > power"

    def test_noise_equals_power_outputs_zero(self, monkeypatch):
        target = np.array([[1 + 0j]], dtype=np.complex64)
        result = run(monkeypatch, target, noise_value=1.0)
        assert result[0, 0] == 0.0


class TestGRDDenoising:
    def test_zero_noise_leaves_amplitude_unchanged(self, monkeypatch):
        """With zero noise the function is an identity."""
        target = np.array([[3]], dtype=np.float32)
        result = run(monkeypatch, target, noise_value=0.0, is_grd=True)
        np.testing.assert_allclose(result, target, atol=1e-6)

    def test_output_magnitude_reduced_by_noise(self, monkeypatch):
        """Noise must reduce, never increase, the magnitude."""
        target = np.array([[5]], dtype=np.float32)  # power = 25
        result = run(monkeypatch, target, noise_value=9.0, is_grd=True)  # corrected power = 16
        np.testing.assert_allclose(np.abs(result[0, 0]), 4.0, atol=1e-6)

    def test_power_exceeds_noise_exact_formula(self, monkeypatch):
        """Verify exact analytic value: |out| = sqrt(power - noise)."""
        amplitude, noise = 5.0, 9.0
        target = np.array([[amplitude]], dtype=np.float32)
        result = run(monkeypatch, target, noise_value=noise, is_grd=True)
        expected = np.sqrt(amplitude**2 - noise)  # sqrt(16) = 4
        np.testing.assert_allclose(np.abs(result[0, 0]), expected, atol=1e-6)

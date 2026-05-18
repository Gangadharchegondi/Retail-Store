"""
Weight sensor service module - handles security weight verification
"""
import random
from backend.config import WEIGHT_DEVIATION_THRESHOLD, WEIGHT_NOISE_RANGE

expected_weight = 0.0


def update_expected_weight(weight):
    """Add weight to expected total."""
    global expected_weight
    expected_weight += weight


def reset_weight():
    """Reset expected weight to zero."""
    global expected_weight
    expected_weight = 0.0


def get_expected_weight():
    """Get current expected weight."""
    return expected_weight


def check_theft_status(expected_weight_value):
    """
    Simulate a scale reading and check for weight mismatches (potential theft).
    
    Args:
        expected_weight_value: Expected total weight in grams
        
    Returns:
        Dictionary with alert status and actual weight reading
    """
    # Simulated sensor noise
    actual = expected_weight_value + random.uniform(-WEIGHT_NOISE_RANGE, WEIGHT_NOISE_RANGE)
    
    if expected_weight_value > 0 and abs(actual - expected_weight_value) > WEIGHT_DEVIATION_THRESHOLD:
        return {
            "alert": "⚠️ Security Alert: Item weight mismatch!",
            "actual_weight": actual
        }
    
    return {
        "status": "Weight verified",
        "actual_weight": actual
    }

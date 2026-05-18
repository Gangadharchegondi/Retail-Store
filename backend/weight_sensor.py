import random

expected_weight = 0.0

def update_expected_weight(weight):
    global expected_weight
    expected_weight += weight

def reset_weight():
    global expected_weight
    expected_weight = 0.0

def get_expected_weight():
    return expected_weight

def check_theft_status(expected_weight):
    """Simulates a scale reading and checks for mismatches."""
    # Simulated noise (+/- 5g)
    actual = expected_weight + random.uniform(-5, 5)
    
    if expected_weight > 0 and abs(actual - expected_weight) > 35:
        return {"alert": "⚠️ Security Alert: Item weight mismatch!", "actual_weight": actual}
    
    return {"status": "Weight verified", "actual_weight": actual}